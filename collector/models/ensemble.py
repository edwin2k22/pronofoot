"""
MODÈLE D'ENSEMBLE 1N2 + AUTO-APPRENTISSAGE.

Au lieu d'un seul modèle, on fait voter plusieurs sous-modèles indépendants, puis
on pondère chacun selon sa PERFORMANCE RÉELLE mesurée sur les matchs déjà joués
(auto-apprentissage). Enfin une couche de CALIBRATION recale les probabilités et
corrige la sous-estimation structurelle des matchs NULS (42 % des matchs CDM).

Sous-modèles (tous dérivés de données réelles) :
  • elo      : probabilités issues du seul écart Elo (force globale)
  • grid     : probabilités issues de la grille Dixon-Coles (buts/xG attendus)
  • form     : probabilités issues de la forme récente réelle (pts sur 10 derniers)
  • market   : probabilités implicites des cotes 1N2, déviguées et plafonnées

Apprentissage : ensemble_weights.json garde les poids + la perf (log-loss) de chaque
sous-modèle. À chaque recalcul, on ré-pondère vers le sous-modèle le plus fiable.

RÈGLE N°1 : tout vient de données réelles, rien n'est inventé. Tant que peu de
matchs sont joués, les poids restent proches d'un prior neutre (shrinkage).
"""
from __future__ import annotations
import os, json, math

WFILE = os.path.join(os.path.dirname(__file__), "..", "data", "ensemble_weights.json")

# poids de départ (prior) avant apprentissage
DEFAULT_WEIGHTS = {"elo": 0.32, "grid": 0.33, "form": 0.20, "market": 0.15}
MAX_MARKET_WEIGHT = 0.24
DRAW_BIAS_GRID = [-0.04, -0.02, 0.0, 0.02, 0.04, 0.06, 0.08, 0.10, 0.12]
# remontée structurelle du nul : les modèles à base de buts sous-estiment l'égalité.
# borne calibrée empiriquement (CDM ≈ 30-42 % de nuls selon les phases).
DRAW_FLOOR = 0.24            # un match n'a quasi jamais < 24 % de chance de nul
DRAW_BOOST_TIGHT = 0.06      # bonus de nul quand les 2 équipes sont proches (Elo)


def _norm3(p1, px, p2):
    s = p1 + px + p2
    if s <= 0:
        return 1/3, 1/3, 1/3
    return p1/s, px/s, p2/s


def _normalize_weights(weights, active=None):
    """Merge legacy weights, optionally remove inactive models, and cap market impact."""
    active = set(active or DEFAULT_WEIGHTS)
    merged = {k: float((weights or {}).get(k, DEFAULT_WEIGHTS[k]))
              for k in DEFAULT_WEIGHTS if k in active}
    if not merged:
        merged = dict(DEFAULT_WEIGHTS)

    if "market" in merged and merged["market"] > MAX_MARKET_WEIGHT:
        surplus = merged["market"] - MAX_MARKET_WEIGHT
        merged["market"] = MAX_MARKET_WEIGHT
        others = [k for k in merged if k != "market"]
        base = sum(merged[k] for k in others)
        if others and base > 0:
            for k in others:
                merged[k] += surplus * merged[k] / base

    s = sum(max(0.0, v) for v in merged.values()) or 1.0
    return {k: max(0.0, v) / s for k, v in merged.items()}


def elo_probs(elo_h, elo_a, home_adv=55.0):
    """1N2 à partir du seul Elo. Le nul est dérivé de la proximité des forces."""
    d = (elo_h + home_adv) - elo_a
    p_h_nodraw = 1.0 / (1.0 + 10 ** (-d/400.0))     # proba que H batte A (hors nul)
    # part du nul : maximale quand les forces sont égales, décroît avec |d|
    p_draw = 0.30 * math.exp(-(d**2) / (2*250.0**2))
    p1 = p_h_nodraw * (1 - p_draw)
    p2 = (1 - p_h_nodraw) * (1 - p_draw)
    return _norm3(p1, p_draw, p2)


def form_probs(form_h, form_a, home_adv=0.06):
    """1N2 à partir de la forme récente réelle (form_index ∈ [0,1])."""
    fh = (form_h if form_h is not None else 0.5) + home_adv
    fa = (form_a if form_a is not None else 0.5)
    diff = fh - fa
    p_h_nodraw = 1.0 / (1.0 + math.exp(-4.0*diff))
    p_draw = 0.28 * math.exp(-(diff**2)/(2*0.25**2))
    p1 = p_h_nodraw * (1 - p_draw)
    p2 = (1 - p_h_nodraw) * (1 - p_draw)
    return _norm3(p1, p_draw, p2)


def market_probs(odd1, oddX, odd2, max_overround=0.18):
    """
    1N2 from bookmaker odds after removing the overround.

    This is a calibration voice, not a blind copy of the market. Very high-margin or
    incomplete odds are ignored so the ensemble stays driven by football signals.
    """
    odds = (odd1, oddX, odd2)
    try:
        if any(o is None or float(o) <= 1.01 for o in odds):
            return None
        implied = [1.0 / float(o) for o in odds]
    except (TypeError, ValueError, ZeroDivisionError):
        return None

    book = sum(implied)
    if book <= 0 or book > 1.0 + max_overround:
        return None
    return _norm3(implied[0], implied[1], implied[2])


def load_weights():
    try:
        with open(WFILE, encoding="utf-8") as f:
            d = json.load(f)
        w = d.get("weights", DEFAULT_WEIGHTS)
        return _normalize_weights(w), d
    except (OSError, ValueError):
        return dict(DEFAULT_WEIGHTS), {}


def combine(elo_p, grid_p, form_p, market_p=None, weights=None, elo_d=0.0):
    """
    Mélange pondéré des sous-modèles + correction du nul.
    elo_p/grid_p/form_p/market_p : tuples (p1,pX,p2).
    elo_d : écart Elo (pour le bonus nul serré).
    """
    models = {"elo": elo_p, "grid": grid_p, "form": form_p}
    if market_p:
        models["market"] = market_p
    w = _normalize_weights(weights or DEFAULT_WEIGHTS, active=models.keys())
    p1 = sum(w[k] * models[k][0] for k in models)
    px = sum(w[k] * models[k][1] for k in models)
    p2 = sum(w[k] * models[k][2] for k in models)
    p1, px, p2 = _norm3(p1, px, p2)

    # --- correction structurelle du nul ---
    # 1) bonus si match serré (faible écart Elo) -> plus de chances d'égalité
    tight = math.exp(-(elo_d**2)/(2*120.0**2))         # 1 si Elo égaux, ->0 si écart fort
    px += DRAW_BOOST_TIGHT * tight
    # 2) plancher de nul (jamais sous DRAW_FLOOR sur un match équilibré)
    floor = DRAW_FLOOR * tight
    if px < floor:
        px = floor
    p1, px, p2 = _norm3(p1, px, p2)
    return {"p1": round(p1, 4), "pX": round(px, 4), "p2": round(p2, 4),
            "weights": w, "tight": round(tight, 3)}


def apply_temperature(p1, px, p2, T):
    """Recalibrage par température : T>1 adoucit (modèle trop confiant), T<1 accentue."""
    if T is None or abs(T-1.0) < 1e-6:
        return p1, px, p2
    q1 = max(p1, 1e-9) ** (1.0/T)
    qx = max(px, 1e-9) ** (1.0/T)
    q2 = max(p2, 1e-9) ** (1.0/T)
    return _norm3(q1, qx, q2)


def apply_draw_bias(p1, px, p2, bias):
    """Apply the empirical draw correction learned from finished matches."""
    if bias is None or abs(bias) < 1e-9:
        return _norm3(p1, px, p2)
    px = max(0.02, min(0.65, px + bias))
    return _norm3(p1, px, p2)


def learn_temperature(samples):
    """
    Trouve la température qui minimise le log-loss sur les matchs joués.
    samples : liste de {p1,pX,p2,outcome}. Shrinkage vers T=1 (petit échantillon).
    """
    if not samples:
        return 1.0, {"n": 0, "drawBias": 0.0}
    def ll(T, draw_bias):
        tot = 0.0
        for s in samples:
            p1, px, p2 = apply_temperature(s["p1"], s["pX"], s["p2"], T)
            p1, px, p2 = apply_draw_bias(p1, px, p2, draw_bias)
            key = {"1": p1, "X": px, "2": p2}[s["outcome"]]
            tot += -math.log(max(1e-9, key))
        return tot/len(samples)
    best_T, best_bias, best = 1.0, 0.0, ll(1.0, 0.0)
    T = 0.6
    while T <= 2.0001:
        for draw_bias in DRAW_BIAS_GRID:
            v = ll(T, draw_bias)
            if v < best:
                best, best_T, best_bias = v, T, draw_bias
        T += 0.05
    # shrinkage vers 1.0 selon la taille d'échantillon
    n = len(samples)
    temp_k = 15.0
    draw_k = 30.0
    temp_a = n/(n+temp_k)
    draw_a = n/(n+draw_k)
    T_shrunk = round(temp_a*best_T + (1-temp_a)*1.0, 3)
    draw_shrunk = round(draw_a*best_bias, 4)
    return T_shrunk, {"n": n, "bestRaw": round(best_T, 2),
                      "drawBias": draw_shrunk,
                      "drawBiasRaw": round(best_bias, 3),
                      "logloss": round(best, 4)}


def _logloss(probs, outcome):
    """log-loss d'une prédiction (outcome ∈ {'1','X','2'})."""
    key = {"1": "p1", "X": "pX", "2": "p2"}[outcome]
    p = max(1e-6, min(1-1e-6, probs[key]))
    return -math.log(p)


def learn(all_matches, base_predict_fn):
    """
    Auto-apprentissage : sur les matchs joués, mesure le log-loss de chaque sous-modèle
    et re-pondère (poids ∝ 1/logloss), avec shrinkage vers le prior tant que n est petit.
    base_predict_fn(m) -> dict {elo:(...), grid:(...), form:(...), outcome:'1'|'X'|'2'}
    """
    fin = [m for m in all_matches if m.get("status") == "FINISHED" and m.get("analysis")]
    sub = {k: [] for k in DEFAULT_WEIGHTS}
    for m in fin:
        row = base_predict_fn(m)
        if not row:
            continue
        for k in DEFAULT_WEIGHTS:
            if not row.get(k):
                continue
            sub[k].append(_logloss({"p1": row[k][0], "pX": row[k][1], "p2": row[k][2]},
                                   row["outcome"]))
    n = len(fin)
    if n == 0:
        return dict(DEFAULT_WEIGHTS), {"n": 0, "logloss": {}}

    avg = {k: (sum(v)/len(v) if v else None) for k, v in sub.items()}
    available = [k for k, v in sub.items() if v]
    target = dict(DEFAULT_WEIGHTS)
    if available:
        # poids ∝ inverse du log-loss (meilleur = plus faible log-loss)
        inv = {k: 1.0/max(0.01, avg[k]) for k in available}
        s = sum(inv.values()) or 1.0
        learned_available = {k: inv[k]/s for k in available}
        prior_mass = sum(DEFAULT_WEIGHTS[k] for k in available)
        for k in available:
            target[k] = learned_available[k] * prior_mass
    target = _normalize_weights(target)
    # shrinkage vers le prior : k_eff = n/(n+K)
    K = 12.0
    a = n/(n+K)
    blended = {k: a*target[k] + (1-a)*DEFAULT_WEIGHTS[k] for k in DEFAULT_WEIGHTS}
    blended = _normalize_weights(blended)
    meta = {"n": n,
            "logloss": {k: round(v, 4) for k, v in avg.items() if v is not None},
            "samples": {k: len(v) for k, v in sub.items()},
            "learnedRaw": {k: round(target[k], 3) for k in target},
            "marketWeightCap": MAX_MARKET_WEIGHT}
    return blended, meta


def save_weights(weights, meta):
    os.makedirs(os.path.dirname(WFILE), exist_ok=True)
    with open(WFILE, "w", encoding="utf-8") as f:
        json.dump({"weights": _normalize_weights(weights), "meta": meta},
                  f, ensure_ascii=False, indent=2)

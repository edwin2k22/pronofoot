"""
Calibration automatique de ρ (Dixon-Coles) et γ (effet de choc) sur les vrais
résultats du tournoi, par MAXIMUM DE VRAISEMBLANCE.

Principe : pour chaque match terminé, on connaît le λ/μ qu'on AVAIT estimé avant le
match et le score RÉEL. On cherche les (ρ, γ) qui maximisent la probabilité jointe
des scores réellement observés sous le modèle corrigé (score_grid).

Au fil du tournoi, ρ et γ s'ajustent aux données réelles plutôt que de rester figés
sur les valeurs de littérature. Prudence : tant qu'il y a peu de matchs, on reste
proche du prior (shrinkage vers les valeurs par défaut).

Sortie : collector/data/calibration.json -> {rho, gamma, n_matches, log_likelihood}
lu par le pipeline pour alimenter score_grid.
"""
from __future__ import annotations
import os, json, math

from . import score_grid as sg

DATA = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
OUT = os.path.join(DATA, "calibration.json")

# grilles de recherche (raisonnables d'après la littérature)
RHO_GRID = [-0.12, -0.10, -0.08, -0.06, -0.04, -0.02, 0.0]
GAMMA_GRID = [0.0, 0.03, 0.06, 0.09, 0.12]

# priors (valeurs par défaut) + force du shrinkage
PRIOR_RHO, PRIOR_GAMMA = sg.DEFAULT_RHO, 0.05
PRIOR_WEIGHT = 8          # équivaut à ~8 "matchs virtuels" tirant vers le prior


def _log_likelihood(samples, rho, gamma):
    """
    Somme des log P(score_réel | λ, μ, ρ, γ) sur les matchs observés.
    samples : liste de (lam, mu, gh, ga).
    """
    ll = 0.0
    for lam, mu, gh, ga in samples:
        if gh > sg.MAXG or ga > sg.MAXG:
            continue
        grid = sg.score_grid(lam, mu, rho, gamma)
        p = grid[gh][ga]
        ll += math.log(max(p, 1e-9))
    return ll


def calibrate(samples) -> dict:
    """
    Recherche (ρ, γ) maximisant la vraisemblance, avec shrinkage vers le prior
    quand peu de matchs. samples : (lam_estimé, mu_estimé, buts_home, buts_away).
    """
    n = len(samples)
    if n == 0:
        return {"rho": PRIOR_RHO, "gamma": PRIOR_GAMMA, "n_matches": 0,
                "log_likelihood": None, "note": "aucun match -> prior"}

    best = None
    for rho in RHO_GRID:
        for gamma in GAMMA_GRID:
            ll = _log_likelihood(samples, rho, gamma)
            if best is None or ll > best[2]:
                best = (rho, gamma, ll)
    rho_mle, gamma_mle, ll = best

    # shrinkage : (n·MLE + k·prior) / (n+k)
    k = PRIOR_WEIGHT
    rho_final = round((n * rho_mle + k * PRIOR_RHO) / (n + k), 4)
    gamma_final = round((n * gamma_mle + k * PRIOR_GAMMA) / (n + k), 4)

    return {"rho": rho_final, "gamma": gamma_final, "n_matches": n,
            "rho_mle": rho_mle, "gamma_mle": gamma_mle,
            "log_likelihood": round(ll, 2),
            "note": f"calibré sur {n} matchs (shrinkage k={k} vers prior)"}


# -------- ajustement empirique BTTS / Over (biais de marché) --------
# Prudence maximale : très peu de matchs => fort shrinkage. On ne corrige que le
# BIAIS SYSTÉMATIQUE moyen (predicted - observed), pas chaque match individuel.
BIAS_PRIOR_WEIGHT = 12     # ~12 matchs virtuels neutres -> tire la correction vers 0


def bias_adjust(market_preds, observed):
    """
    market_preds : liste des probabilités prédites (ex. btts) AVANT match
    observed     : liste de 0/1 réellement observés (même ordre)
    Renvoie un décalage additif borné, fortement réduit par shrinkage tant que
    n est petit. correction = (somme(obs-pred)) / (n + k).  borné à ±0.15.
    """
    n = len(market_preds)
    if n == 0:
        return {"shift": 0.0, "n": 0, "note": "aucun match -> pas de correction"}
    raw = sum(o - p for p, o in zip(market_preds, observed))   # biais cumulé
    shift = raw / (n + BIAS_PRIOR_WEIGHT)                       # shrinkage fort
    shift = max(-0.15, min(0.15, shift))                       # borne de sécurité
    return {"shift": round(shift, 4), "n": n,
            "avg_pred": round(sum(market_preds) / n, 3),
            "avg_obs": round(sum(observed) / n, 3),
            "note": f"biais empirique sur {n} matchs (shrinkage k={BIAS_PRIOR_WEIGHT}, borné ±0.15)"}


def scale_factor(pred_totals, real_totals, prior_factor=1.0, k=6):
    """
    Facteur multiplicatif empirique pour un total (ex. corners) : le modèle peut
    surestimer/sous-estimer systématiquement vs le réel. On calcule le ratio
    (somme réel / somme prédit), tiré vers 1.0 par shrinkage (k matchs virtuels).
    Borné [0.5, 1.6]. Sert à corriger les corners (source FootyStats biaisée).
    """
    n = len(pred_totals)
    sp = sum(pred_totals)
    sr = sum(real_totals)
    if n == 0 or sp <= 0:
        return {"factor": round(prior_factor, 3), "n": 0, "note": "aucun match -> facteur neutre"}
    raw = sr / sp
    factor = (n * raw + k * prior_factor) / (n + k)        # shrinkage vers 1.0
    factor = max(0.5, min(1.6, factor))
    return {"factor": round(factor, 3), "n": n,
            "avg_pred": round(sp / n, 2), "avg_obs": round(sr / n, 2),
            "raw": round(raw, 3),
            "note": f"facteur empirique sur {n} matchs (shrinkage k={k}, borné [0.5,1.6])"}


def _parse_score(value):
    try:
        h, a = str(value).strip().split("-", 1)
        return int(h), int(a)
    except (TypeError, ValueError):
        return None


def score_factors_from_predictions(matches, prior_weight=48.0,
                                   min_factor=0.65, max_factor=1.45) -> dict:
    """
    Calibre les scores exacts à partir des anciennes prédictions sauvegardées.

    Pour chaque match terminé, on reconstruit la grille pré-match via lamHome/lamAway
    et le rho/gamma stocké au moment du prono, puis on compare la masse attendue par
    score exact aux scores réellement observés. Les facteurs sont fortement shrinkés
    vers 1.0 pour éviter de surapprendre sur un petit tournoi.
    """
    expected = {f"{i}-{j}": 0.0 for i in range(sg.MAXG + 1) for j in range(sg.MAXG + 1)}
    observed = {k: 0 for k in expected}
    samples = []
    for m in matches or []:
        p = (m or {}).get("prediction") or {}
        real = ((m or {}).get("analysis") or {}).get("realScore") or (m or {}).get("realScore")
        parsed = _parse_score(real)
        if not parsed:
            continue
        try:
            lam = float(p.get("lamHome"))
            mu = float(p.get("lamAway"))
        except (TypeError, ValueError):
            continue
        dc = p.get("dixonColes") or {}
        try:
            rho = float(dc.get("rho", PRIOR_RHO))
            gamma = float(dc.get("gamma", PRIOR_GAMMA))
        except (TypeError, ValueError):
            rho, gamma = PRIOR_RHO, PRIOR_GAMMA
        grid = sg.score_grid(lam, mu, rho=rho, gamma=gamma)
        for i in range(sg.MAXG + 1):
            for j in range(sg.MAXG + 1):
                expected[f"{i}-{j}"] += grid[i][j]
        gh, ga = parsed
        if 0 <= gh <= sg.MAXG and 0 <= ga <= sg.MAXG:
            observed[f"{gh}-{ga}"] += 1
        samples.append((grid, gh, ga))

    n = len(samples)
    if n == 0:
        return {"n": 0, "factors": {}, "note": "aucun ancien prono exploitable -> neutre"}

    factors = {}
    details = []
    for score, exp_count in expected.items():
        # prior en "match-equivalents" proportionnel à la masse attendue de la case.
        prior = exp_count * (prior_weight / max(n, 1))
        denom = exp_count + prior
        if denom <= 0:
            factor = 1.0
        else:
            factor = (observed[score] + prior) / denom
        factor = max(min_factor, min(max_factor, factor))
        factors[score] = round(factor, 3)
        if observed[score] or abs(factor - 1.0) >= 0.08:
            details.append({
                "score": score,
                "observed": observed[score],
                "expected": round(exp_count, 2),
                "factor": round(factor, 3),
            })

    def _prob_at(grid, gh, ga):
        if 0 <= gh <= sg.MAXG and 0 <= ga <= sg.MAXG:
            return max(grid[gh][ga], 1e-9)
        return 1e-9

    ll_before = []
    ll_after = []
    hit1_before = hit1_after = 0
    hit5_before = hit5_after = 0
    for grid, gh, ga in samples:
        adj = sg.apply_score_factors(grid, factors)
        ll_before.append(-math.log(_prob_at(grid, gh, ga)))
        ll_after.append(-math.log(_prob_at(adj, gh, ga)))
        before_scores = [c["score"] for c in sg.derived_markets(grid)["topScores"]]
        after_scores = [c["score"] for c in sg.derived_markets(adj)["topScores"]]
        real = f"{gh}-{ga}"
        hit1_before += int(before_scores[:1] == [real])
        hit1_after += int(after_scores[:1] == [real])
        hit5_before += int(real in before_scores[:5])
        hit5_after += int(real in after_scores[:5])

    details.sort(key=lambda x: (abs(x["factor"] - 1.0), x["observed"]), reverse=True)
    return {
        "n": n,
        "priorWeight": prior_weight,
        "factorBounds": [min_factor, max_factor],
        "factors": factors,
        "topAdjustments": details[:12],
        "eval": {
            "logLossBefore": round(sum(ll_before) / n, 4),
            "logLossAfter": round(sum(ll_after) / n, 4),
            "top1Before": round(hit1_before / n, 4),
            "top1After": round(hit1_after / n, 4),
            "top5Before": round(hit5_before / n, 4),
            "top5After": round(hit5_after / n, 4),
        },
        "note": f"calibration score exact sur {n} anciens pronos (shrinkage k={prior_weight}, facteurs bornés)",
    }


def save(result: dict):
    os.makedirs(DATA, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


def load() -> dict:
    """Charge la calibration courante, ou les priors si absente."""
    if os.path.exists(OUT):
        try:
            with open(OUT, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"rho": PRIOR_RHO, "gamma": PRIOR_GAMMA, "n_matches": 0}

#!/usr/bin/env python3
"""
Pipeline ProноFoot — système Bayésien évolutif (les 6 points).

  seed     : remplit la base locale avec le calendrier réel (1) + priors Elo/FIFA (2)
  ingest   : enregistre les résultats réels + stats (4) depuis openfootball
  update   : recalcule les ratings Elo (4) avec pondération progressive (5)
  predict  : génère predictions.json via les 4 modèles séparés (3)
  run      : tout enchaîner

Base locale SQLite (6) -> robustesse, pas de dépendance réseau permanente.

Usage :
    python3 -m collector.pipeline seed
    python3 -m collector.pipeline run      # ingest + update + predict
"""
from __future__ import annotations
import sys, os, json, argparse, re
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collector.db import database as db
from collector.models import elo as elo_mod
from collector.models import shrinkage as shr
from collector.models import markets
from collector.models import lineup_impact as li
from collector.models import context as ctx
from collector.models import standings as stand
from collector.models import score_grid as sg
from collector.models import knockout as ko
from collector.models import upset as upset_mod
from collector.models import attack_quality as atkq
from collector.models import defense_quality as defq
from collector.models import availability as avail
from collector.models import ensemble as ens
from collector.models import calibrate as calib
from collector.models import player_props as pprops
from collector.models import nlp_momentum as nlpm
from collector.sources import player_bios as pbios
from collector.sources import openfootball_wc as wc
from collector.sources import squads_2026
from collector.sources import recent_form as rform
from collector.sources import referees_2026 as refs
from collector.sources import referee_form as refform
from collector.sources import team_setpieces as setp
from collector.sources.team_ratings import get_rating

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

# priors neutres de Coupe du Monde (moyennes historiques connues, sans dataset 2018/2022)
PRIOR = {"gf": 1.35, "ga": 1.35, "xg": 1.35, "corners": 5.0, "cards": 2.0,
         "shots": 13.6, "shots_on": 4.4, "possession": 50.0, "accuracy": 0.34}
VALUE_EDGE_MIN = {"1N2": 0.20, "OU": 0.15, "BTTS": 0.12, "CORNERS": 0.15}
# tirs/cadrés par équipe + possession + précision (cadrés/tirs) — moyennes réelles CDM 2026


# ---------- (1)+(2) SEED ----------
def seed():
    conn = db.init_db()
    sched = wc.load_schedule()
    print(f"  priors CDM : {PRIOR['corners']} corners, {PRIOR['cards']} cartons, "
          f"{PRIOR['gf']} buts /équipe/match")
    n_teams = n_matches = 0
    for m in sched.get("matches", []):
        t1, t2 = m.get("team1"), m.get("team2")
        if not t1 or not t2 or any(c in t1 for c in "0123456789/"):
            continue  # placeholders knockout
        for t in (t1, t2):
            r = get_rating(t)
            db.upsert_team(conn, t, elo=r, fifa_prior=r)
            # forme récente RÉELLE (10 derniers matchs) -> initialise gf/ga avant tout match CDM
            ff = rform.team_form(t)
            if ff:
                conn.execute("UPDATE teams SET gf_avg=?, ga_avg=? WHERE name=? AND matches_played=0",
                             (ff["gf_avg"], ff["ga_avg"], t))
        db.upsert_match(conn, "CDM 2026", m.get("group", m.get("round", "")),
                        f"{m.get('date','')} {m.get('time','')}".strip(), t1, t2,
                        status="SCHEDULED")  # statut réel posé par ingest()
        n_matches += 1
    # init compteur équipes
    n_teams = len(db.all_teams(conn))

    # effectifs RÉELS 2026 (joueurs sélectionnés ; stats N/D jusqu'aux matchs)
    n_players = 0
    for pl in squads_2026.all_players():
        db.upsert_player(conn, pl["name"], pl["team"], pl["number"],
                         pl["pos"], pl["dob"], pl["age"])
        n_players += 1

    conn.commit(); conn.close()
    print(f"✅ seed : {n_teams} équipes (priors Elo/FIFA), {n_matches} matchs (calendrier réel), "
          f"{n_players} joueurs sélectionnés 2026.")


# ---------- (4) INGEST résultats réels ----------
def ingest():
    """Récupère les scores réels depuis openfootball et les écrit en base."""
    conn = db.init_db()
    sched = wc.load_schedule()
    updated = 0
    for m in sched.get("matches", []):
        ft = m.get("score", {}).get("ft")
        if not ft:
            continue
        t1, t2 = m.get("team1"), m.get("team2")
        if not t1 or not t2:
            continue
        date = f"{m.get('date','')} {m.get('time','')}".strip()
        row = conn.execute(
            "SELECT id, status FROM matches WHERE home=? AND away=? AND utc_date=?",
            (t1, t2, date)).fetchone()
        if row and row["status"] != "FINISHED":
            # openfootball ne fournit pas xG/corners -> on laisse NULL (le modèle gère)
            stats = {"home_goals": ft[0], "away_goals": ft[1]}
            ht = m.get("score", {}).get("ht")
            if ht and len(ht) == 2:
                stats["home_ht_goals"] = ht[0]
                stats["away_ht_goals"] = ht[1]
            db.record_result(conn, row["id"], **stats)
            updated += 1
    conn.commit(); conn.close()
    print(f"✅ ingest : {updated} nouveaux résultats réels enregistrés.")


# ---------- (4)+(5) UPDATE ratings ----------
def update():
    conn = db.init_db()
    todo = db.unprocessed_finished(conn)
    for mt in todo:
        h, a = db.get_team(conn, mt["home"]), db.get_team(conn, mt["away"])
        if not h or not a or mt["home_goals"] is None or mt["away_goals"] is None:
            db.mark_processed(conn, mt["id"]); continue
        # 1) Elo (avec K décroissant = anti-overreaction)
        new_h, new_a = elo_mod.update_pair(
            h["elo"], a["elo"], mt["home_goals"], mt["away_goals"],
            mt["home_xg"], mt["away_xg"], h["matches_played"], a["matches_played"])
        db.log_rating(conn, h["name"], mt["id"], h["elo"], new_h, "match result")
        db.log_rating(conn, a["name"], mt["id"], a["elo"], new_a, "match result")

        # 2) moyennes évolutives (running mean) + compteur
        gh, ga = mt["home_goals"], mt["away_goals"]
        hm_gf, _ = shr.update_running_mean(h["gf_avg"], h["matches_played"], gh)
        hm_ga, _ = shr.update_running_mean(h["ga_avg"], h["matches_played"], ga)
        am_gf, _ = shr.update_running_mean(a["gf_avg"], a["matches_played"], ga)
        am_ga, hp_new = shr.update_running_mean(a["ga_avg"], a["matches_played"], gh)
        # xG réel (si dispo) -> moyennes xG marqué / encaissé par équipe
        hxg, axg = mt["home_xg"], mt["away_xg"]
        hm_xg = shr.update_running_mean(h["xg_avg"], h["matches_played"], hxg)[0] if hxg is not None else h["xg_avg"]
        hm_xga = shr.update_running_mean(h["xga_avg"], h["matches_played"], axg)[0] if axg is not None else h["xga_avg"]
        am_xg = shr.update_running_mean(a["xg_avg"], a["matches_played"], axg)[0] if axg is not None else a["xg_avg"]
        am_xga = shr.update_running_mean(a["xga_avg"], a["matches_played"], hxg)[0] if hxg is not None else a["xga_avg"]

        # TIRS / TIRS CADRÉS : moyennes évolutives marqués + concédés (running mean).
        # _rm(col, valeur) ne met à jour QUE si la stat réelle existe (sinon garde l'ancienne).
        def _rm(team, col, val):
            if val is None:
                return team[col]
            if team[col] is None:
                return float(val)
            return shr.update_running_mean(team[col], team["matches_played"], val)[0]
        hs, as_ = mt["home_shots"], mt["away_shots"]
        hso, aso = mt["home_shots_on"], mt["away_shots_on"]
        h_shots = _rm(h, "shots_avg", hs)
        h_shots_ag = _rm(h, "shots_against_avg", as_)
        h_son = _rm(h, "shots_on_avg", hso)
        h_son_ag = _rm(h, "shots_on_against_avg", aso)
        a_shots = _rm(a, "shots_avg", as_)
        a_shots_ag = _rm(a, "shots_against_avg", hs)
        a_son = _rm(a, "shots_on_avg", aso)
        a_son_ag = _rm(a, "shots_on_against_avg", hso)
        # POSSESSION moyenne (depuis team_stats_json) — running mean
        _ts = {}
        try:
            _ts = json.loads(mt["team_stats_json"]) if ("team_stats_json" in mt.keys() and mt["team_stats_json"]) else {}
        except (TypeError, ValueError):
            _ts = {}
        h_poss = _rm(h, "possession_avg", _ts.get("home_possession"))
        a_poss = _rm(a, "possession_avg", _ts.get("away_possession"))
        h_fouls = _rm(h, "fouls_avg", _ts.get("home_fouls"))
        a_fouls = _rm(a, "fouls_avg", _ts.get("away_fouls"))

        conn.execute("""UPDATE teams SET elo=?, gf_avg=?, ga_avg=?, xg_avg=?, xga_avg=?,
                        shots_avg=?, shots_against_avg=?, shots_on_avg=?, shots_on_against_avg=?,
                        possession_avg=?, fouls_avg=?,
                        matches_played=matches_played+1, updated_at=? WHERE name=?""",
                     (new_h, hm_gf, hm_ga, hm_xg, hm_xga,
                      h_shots, h_shots_ag, h_son, h_son_ag, h_poss, h_fouls, db.now(), h["name"]))
        conn.execute("""UPDATE teams SET elo=?, gf_avg=?, ga_avg=?, xg_avg=?, xga_avg=?,
                        shots_avg=?, shots_against_avg=?, shots_on_avg=?, shots_on_against_avg=?,
                        possession_avg=?, fouls_avg=?,
                        matches_played=matches_played+1, updated_at=? WHERE name=?""",
                     (new_a, am_gf, am_ga, am_xg, am_xga,
                      a_shots, a_shots_ag, a_son, a_son_ag, a_poss, a_fouls, db.now(), a["name"]))
        db.mark_processed(conn, mt["id"])
    conn.commit()
    print(f"✅ update : {len(todo)} matchs intégrés aux ratings (Elo + moyennes).")
    conn.close()


# ---------- (3) PREDICT via 4 modèles séparés ----------
def _expected_goals(team, opp):
    """
    λ via moyennes shrinkées (point 5) modulées par l'écart Elo.
    Source de force : rating Elo (prior FIFA) + buts marqués/encaissés CDM 2026
    (remplis au fil des matchs joués). Aucune donnée 2018/2022.
    """
    n_t, n_o = team["matches_played"], opp["matches_played"]
    # attaque = buts marqués MÉLANGÉS avec le xG marqué (xG = signal moins bruité).
    # 50/50 buts/xG dès qu'on a des matchs joués (sinon le prior domine via shrink).
    gf = shr.shrink(team["gf_avg"], n_t, PRIOR["gf"])
    xgf = shr.shrink(team["xg_avg"], n_t, PRIOR["xg"])
    att = 0.5 * gf + 0.5 * xgf if n_t > 0 else gf
    ga = shr.shrink(opp["ga_avg"], n_o, PRIOR["ga"])
    xga = shr.shrink(opp["xga_avg"], n_o, PRIOR["xg"])
    deff = 0.5 * ga + 0.5 * xga if n_o > 0 else ga
    lam = (att + deff) / 2
    # modulation par l'écart Elo (force globale, prior FIFA + résultats 2026)
    factor = 10 ** ((team["elo"] - opp["elo"]) / 800.0)
    return max(0.25, min(4.5, lam * factor))


def _safe_json(v):
    """Parse un blob JSON en dict, ou None si vide/invalide."""
    if not v:
        return None
    try:
        return json.loads(v)
    except (ValueError, TypeError):
        return None


def _analyze_finished(mt, h, a, res, goals):
    """Construit l'analyse post-match : prono pré-match vs réalité (le quoi/pourquoi)."""
    gh, ga = mt["home_goals"], mt["away_goals"]
    if gh is None or ga is None:
        return None
    # issue réelle
    if gh > ga:
        outcome, winner = "1", mt["home"]
    elif gh < ga:
        outcome, winner = "2", mt["away"]
    else:
        outcome, winner = "X", None
    # le modèle avait-il vu juste ? (issue la plus probable du prono pré-match)
    probs = {"1": res["p1"], "X": res["pX"], "2": res["p2"]}
    predicted = max(probs, key=probs.get)
    correct = predicted == outcome
    # score exact prédit ?
    exact = (goals["top_score"][0] == gh and goals["top_score"][1] == ga)
    total = gh + ga
    over25_real = total > 2
    btts_real = gh > 0 and ga > 0

    lbl = {"1": mt["home"], "X": "le nul", "2": mt["away"]}
    why = []
    why.append(f"Le modèle donnait <b>{lbl[predicted]}</b> favori ({probs[predicted]*100:.0f}%).")
    if correct:
        why.append("✅ Issue correctement anticipée.")
    else:
        why.append(f"❌ Surprise : c'est <b>{lbl[outcome]}</b> qui l'emporte"
                   if outcome != 'X' else "❌ Surprise : match nul, non anticipé.")
    why.append(f"Score le plus probable prévu : {goals['top_score'][0]}-{goals['top_score'][1]} "
               f"→ réel {gh}-{ga}" + (" (exact !)" if exact else "."))
    why.append(f"Total buts {total} ({'Over' if over25_real else 'Under'} 2.5), "
               f"BTTS {'oui' if btts_real else 'non'}.")

    # déroulé du match (buteurs, cartons, MOTM) si dispo
    events = None
    try:
        if mt["events_json"]:
            events = json.loads(mt["events_json"])
    except (KeyError, TypeError, ValueError):
        events = None

    return {
        "realScore": f"{gh}-{ga}",
        "outcome": outcome, "winner": winner,
        "predictedOutcome": predicted, "predictionCorrect": correct,
        "exactScore": exact,
        "over25Real": over25_real, "bttsReal": btts_real, "totalGoals": total,
        "homeXgReal": mt["home_xg"], "awayXgReal": mt["away_xg"],
        "homeShots": mt["home_shots"], "awayShots": mt["away_shots"],
        "homeShotsOn": mt["home_shots_on"], "awayShotsOn": mt["away_shots_on"],
        "teamStats": _safe_json(mt["team_stats_json"] if "team_stats_json" in mt.keys() else None),
        "homeCorners": mt["home_corners"], "awayCorners": mt["away_corners"],
        "homeCards": mt["home_cards"], "awayCards": mt["away_cards"],
        "events": events,
        "summary": " ".join(why),
    }


def _shots_from_analysis(analysis):
    """Build the display block for real shot data from a finished-match analysis."""
    if not analysis:
        return None
    home_shots = analysis.get("homeShots")
    away_shots = analysis.get("awayShots")
    if home_shots is None or away_shots is None:
        return None

    home_on = analysis.get("homeShotsOn")
    away_on = analysis.get("awayShotsOn")

    def _acc(shots, shots_on):
        return round(shots_on / shots * 100) if (shots and shots_on is not None and shots > 0) else None

    return {
        "home": home_shots,
        "away": away_shots,
        "homeOn": home_on,
        "awayOn": away_on,
        "homeAcc": _acc(home_shots, home_on),
        "awayAcc": _acc(away_shots, away_on),
        "real": True,
    }


def calibrate_dc():
    """
    Calibre ρ (Dixon-Coles) et γ (effet de choc) sur les matchs terminés,
    par maximum de vraisemblance. Utilise le λ/μ d'avant-match (mêmes forces
    qu'au moment du pronostic) vs le score réel observé.
    """
    conn = db.init_db()
    finished = conn.execute(
        "SELECT * FROM matches WHERE status='FINISHED' AND home_goals IS NOT NULL").fetchall()
    samples = []
    corn_pred, corn_real = [], []      # pour le facteur correctif corners
    for mt in finished:
        h, a = db.get_team(conn, mt["home"]), db.get_team(conn, mt["away"])
        if not h or not a:
            continue
        lam_h = _expected_goals(h, a)
        lam_a = _expected_goals(a, h)
        # forme récente (même modulation qu'en prédiction)
        fh = rform.team_form(mt["home"]); fa = rform.team_form(mt["away"])
        if fh:
            lam_h *= (0.90 + fh["form_index"] * 0.20)
        if fa:
            lam_a *= (0.90 + fa["form_index"] * 0.20)
        samples.append((max(0.2, lam_h), max(0.2, lam_a),
                        mt["home_goals"], mt["away_goals"]))
        # corners : total PRÉDIT (priors FootyStats) vs total RÉEL du match
        if mt["home_corners"] is not None and mt["away_corners"] is not None:
            ph = setp.get_corners(mt["home"]) or PRIOR["corners"]
            pa = setp.get_corners(mt["away"]) or PRIOR["corners"]
            corn_pred.append(ph + pa)
            corn_real.append(mt["home_corners"] + mt["away_corners"])
    conn.close()
    result = calib.calibrate(samples)
    result["cornersFactor"] = calib.scale_factor(corn_pred, corn_real)
    # --- biais empirique BTTS / Over 2.5 (prédit avant-match vs observé) ---
    rho_c, gamma_c = result["rho"], result["gamma"]
    btts_pred, btts_obs, over_pred, over_obs = [], [], [], []
    for lam, mu, gh, ga in samples:
        grid = sg.score_grid(lam, mu, rho=rho_c, gamma=gamma_c)
        o = sg.outcomes(grid)
        btts_pred.append(o["btts"]); btts_obs.append(1 if (gh > 0 and ga > 0) else 0)
        over_pred.append(o["over25"]); over_obs.append(1 if (gh + ga) > 2 else 0)
    result["bttsBias"] = calib.bias_adjust(btts_pred, btts_obs)
    result["overBias"] = calib.bias_adjust(over_pred, over_obs)
    try:
        with open(os.path.join(DATA_DIR, "predictions.json"), encoding="utf-8") as f:
            prev_predictions = json.load(f)
    except (OSError, ValueError):
        prev_predictions = []
    result["scoreCalib"] = calib.score_factors_from_predictions(prev_predictions)
    calib.save(result)
    print(f"   ↳ biais BTTS {result['bttsBias']['shift']:+.3f} "
          f"(prévu {result['bttsBias'].get('avg_pred','?')} vs réel {result['bttsBias'].get('avg_obs','?')}) ; "
          f"Over {result['overBias']['shift']:+.3f}")
    sc_eval = result["scoreCalib"].get("eval") or {}
    if sc_eval:
        print(f"   ↳ score exact logloss {sc_eval.get('logLossBefore')} -> {sc_eval.get('logLossAfter')} "
              f"; top5 {sc_eval.get('top5Before')} -> {sc_eval.get('top5After')}")
    print(f"✅ calibrate : ρ={result['rho']} γ={result['gamma']} "
          f"({result['n_matches']} matchs, {result.get('note','')})")
    return result


def _btts_confidence(btts_p, model_conf):
    """
    Confiance sur le pronostic BTTS : combine (a) la netteté du marché — à quel
    point btts s'écarte du 50/50 (un marché proche de 0.5 = peu tranchable) et
    (b) la confiance globale du modèle (métacognition). 100% dérivé, rien d'inventé.
    """
    edge = abs(btts_p - 0.5) * 2          # 0 (pile/face) -> 1 (certitude)
    score = 0.5 * edge + 0.5 * float(model_conf or 0)
    if score >= 0.6:
        label = "élevée"
    elif score >= 0.35:
        label = "moyenne"
    else:
        label = "faible"
    # zone d'indécision : trop proche de 50/50 pour trancher honnêtement
    if abs(btts_p - 0.5) < 0.06:
        pick, label = "indécis", "faible"
    else:
        pick = "Oui" if btts_p >= 0.5 else "Non"
    return {"pick": pick, "score": round(score, 2), "label": label}


_SQUADS_CACHE = None


def _load_squads():
    global _SQUADS_CACHE
    if _SQUADS_CACHE is None:
        try:
            with open(os.path.join(DATA_DIR, "squads_2026.json"), encoding="utf-8") as f:
                data = json.load(f)
            _SQUADS_CACHE = {e["equipe"]: e["joueurs"] for e in data}
        except (OSError, ValueError, KeyError):
            _SQUADS_CACHE = {}
    return _SQUADS_CACHE


_PROJECTED_LINEUPS_CACHE = None


def _load_projected_lineups():
    """Compos probables sourcées (ex: FotMob) utilisées avant le XI officiel."""
    global _PROJECTED_LINEUPS_CACHE
    if _PROJECTED_LINEUPS_CACHE is None:
        try:
            with open(os.path.join(DATA_DIR, "projected_lineups.json"), encoding="utf-8") as f:
                _PROJECTED_LINEUPS_CACHE = json.load(f)
        except (OSError, ValueError):
            _PROJECTED_LINEUPS_CACHE = {}
    return _PROJECTED_LINEUPS_CACHE


def _projected_lineup(home, away):
    data = _load_projected_lineups()
    key = f"{home}|{away}"
    if key in data:
        return data[key]
    rev = f"{away}|{home}"
    src = data.get(rev)
    if not src:
        return None
    return {
        **src,
        "home_formation": src.get("away_formation"),
        "away_formation": src.get("home_formation"),
        "home_xi": src.get("away_xi") or [],
        "away_xi": src.get("home_xi") or [],
        "home_bench": src.get("away_bench") or [],
        "away_bench": src.get("home_bench") or [],
    }


def _normalize_source_tags(match):
    aliases = {
        "ESPN-odds": "ESPN-free-odds",
        "Smarkets": "Smarkets-free-odds",
    }
    tags = []
    for raw in match.get("sources") or []:
        tag = aliases.get(raw, raw)
        if tag and tag not in tags:
            tags.append(tag)
    if "free-mode" not in tags:
        tags.insert(0, "free-mode")
    match["sources"] = tags
    return match


TEAM_DATA_ALIASES = {
    "USA": "United States",
    "Bosnia & Herzegovina": "Bosnia and Herzegovina",
}


def _team_data_key(team, data):
    if team in data:
        return team
    alias = TEAM_DATA_ALIASES.get(team)
    if alias in data:
        return alias
    return team


_PLAYER_STATS_CACHE = None


def _load_player_stats():
    global _PLAYER_STATS_CACHE
    if _PLAYER_STATS_CACHE is None:
        try:
            with open(os.path.join(DATA_DIR, "player_stats_real.json"), encoding="utf-8") as f:
                _PLAYER_STATS_CACHE = json.load(f)
        except (OSError, ValueError):
            _PLAYER_STATS_CACHE = {}
    return _PLAYER_STATS_CACHE


def _team_accuracy(team):
    """Taux de mise au cadre d'une équipe = tirs_cadrés_moyens / tirs_moyens. Borné."""
    sh = team["shots_avg"] if "shots_avg" in team.keys() else None
    so = team["shots_on_avg"] if "shots_on_avg" in team.keys() else None
    if not sh or sh <= 0 or so is None:
        return 0.34
    return max(0.15, min(0.60, so / sh))


_MATCH_STATS_CACHE = None


def _real_referee(home, away):
    """Arbitre RÉEL d'un match (ESPN), depuis match_stats_real.json. None si absent."""
    global _MATCH_STATS_CACHE
    if _MATCH_STATS_CACHE is None:
        try:
            with open(os.path.join(DATA_DIR, "match_stats_real.json"), encoding="utf-8") as f:
                _MATCH_STATS_CACHE = json.load(f)
        except (OSError, ValueError):
            _MATCH_STATS_CACHE = {}
    e = _MATCH_STATS_CACHE.get(f"{home}|{away}") or {}
    return e.get("referee")


# profils tactiques GÉNÉRIQUES (pédagogiques) — clairement étiquetés, AUCUN nom inventé
_RISK_PROFILES = [
    {"role": "Défenseur central", "why": "exposé aux transitions rapides adverses"},
    {"role": "Latéral", "why": "face à un ailier dribbleur, multiplie les duels"},
    {"role": "Milieu défensif", "why": "chargé de couper les contres → fautes tactiques"},
]


def _risk_players(team):
    """
    Joueurs à risque de carton :
      - RÉELS : joueurs déjà avertis/exclus lors des matchs joués (player_stats_real.json)
      - GÉNÉRIQUES : profils tactiques (étiquetés), jamais de joueur inventé.
    """
    real = []
    stats = _load_player_stats().get(team)
    if isinstance(stats, dict):
        for name, st in stats.items():
            card = st.get("cartons") or st.get("cards")
            if card:
                cstr = str(card).lower()
                if "yellow" in cstr or "red" in cstr or "jaune" in cstr or "rouge" in cstr:
                    real.append({
                        "name": name,
                        "pos": st.get("poste"),
                        "card": "🟥 rouge" if "red" in cstr or "rouge" in cstr else "🟨 jaune",
                    })
    return {"real": real, "profiles": _RISK_PROFILES}


def _attach_bios(pp):
    """Ajoute le profil réel (bio/forces/faiblesses) aux joueurs cités, sinon rien (N/D)."""
    if not pp:
        return
    for s in pp.get("scorers", []):
        b = pbios.get_bio(s["name"])
        if b:
            s["bio"] = b
    for a in pp.get("assisters", []):
        b = pbios.get_bio(a["name"])
        if b:
            a["bio"] = b
    if pp.get("creator"):
        b = pbios.get_bio(pp["creator"]["name"])
        if b:
            pp["creator"]["bio"] = b
    if pp.get("keeper"):
        b = pbios.get_bio(pp["keeper"]["name"])
        if b:
            pp["keeper"]["bio"] = b


def _learn_ensemble(rows):
    """
    Auto-apprentissage des poids d'ensemble.
    On apprend des SOUS-MODÈLES tels qu'ils ont été calculés AVANT le résultat :
    on relit l'ancien predictions.json (qui contient prediction.ensemble pour chaque
    match) et on confronte au vrai résultat désormais connu. Honnête et non circulaire.
    """
    import json as _json
    path = os.path.join(DATA_DIR, "predictions.json")
    try:
        with open(path, encoding="utf-8") as f:
            prev = _json.load(f)
    except (OSError, ValueError):
        prev = []
    prev_by = {(m["home"], m["away"]): m for m in prev}
    # vrais résultats actuels
    result = {}
    for r in rows:
        if r["status"] == "FINISHED" and r["home_goals"] is not None:
            hg, ag = r["home_goals"], r["away_goals"]
            result[(r["home"], r["away"])] = "1" if hg > ag else ("2" if ag > hg else "X")

    samples = []
    for key, outcome in result.items():
        pm = prev_by.get(key)
        e = (pm or {}).get("prediction", {}).get("ensemble") if pm else None
        if e and all(k in e for k in ("elo", "grid", "form")):
            sample = {"elo": e["elo"], "grid": e["grid"], "form": e["form"],
                      "outcome": outcome}
            if e.get("market"):
                sample["market"] = e["market"]
            samples.append(sample)

    if not samples:
        w, d = ens.load_weights()
        return w, {"n": 0, "note": "pas encore d'historique ensemble — prior", "T": 1.0}
    weights, meta = ens.learn(
        [{"status": "FINISHED", "analysis": {"ok": 1}, "_s": s} for s in samples],
        lambda m: m["_s"])
    # température de calibration : on reconstruit les probas d'ensemble (avant dampener)
    # pour chaque échantillon, puis on cherche la T qui calibre le mieux.
    temp_samples = []
    for s in samples:
        c = ens.combine(s["elo"], s["grid"], s["form"],
                        market_p=s.get("market"), weights=weights)
        temp_samples.append({"p1": c["p1"], "pX": c["pX"], "p2": c["p2"], "outcome": s["outcome"]})
    T, tmeta = ens.learn_temperature(temp_samples)
    meta["T"] = T
    meta["drawBias"] = tmeta.get("drawBias", 0.0)
    meta["tempMeta"] = tmeta
    ens.save_weights(weights, meta)
    return weights, meta


def load_halftime_shares(conn) -> dict[str, float]:
    """
    Calcule pour chaque équipe la part empirique de buts marqués en 1ère mi-temps.
    Utilise le Bayesian Shrinkage (crédibilité) pour éviter le surapprentissage.
    Prior / baseline globale = 0.42. Force du prior (B) = 5.0 buts.
    """
    rows = conn.execute("""
        SELECT home, away, home_goals, away_goals, home_ht_goals, away_ht_goals
        FROM matches
        WHERE status='FINISHED' AND home_ht_goals IS NOT NULL AND away_ht_goals IS NOT NULL
    """).fetchall()

    stats = {}
    for r in rows:
        h, a = r["home"], r["away"]
        hg, ag = r["home_goals"], r["away_goals"]
        hght, aght = r["home_ht_goals"], r["away_ht_goals"]

        stats.setdefault(h, {"goals_total": 0, "goals_ht": 0})
        stats[h]["goals_total"] += hg
        stats[h]["goals_ht"] += hght

        stats.setdefault(a, {"goals_total": 0, "goals_ht": 0})
        stats[a]["goals_total"] += ag
        stats[a]["goals_ht"] += aght

    B = 5.0
    PRIOR = 0.42
    shares = {}
    all_t = conn.execute("SELECT name FROM teams").fetchall()
    for t in all_t:
        name = t["name"]
        if name in stats:
            g_tot = stats[name]["goals_total"]
            g_ht = stats[name]["goals_ht"]
            shares[name] = (g_ht + B * PRIOR) / (g_tot + B)
        else:
            shares[name] = PRIOR
    return shares


def _calculate_trends(conn, h_name, a_name):
    trends = []
    
    def _team_trends(team):
        rows = conn.execute("SELECT home_goals, away_goals, home_corners, away_corners, home, away FROM matches WHERE (home=? OR away=?) AND status='FINISHED' ORDER BY utc_date DESC LIMIT 10", (team, team)).fetchall()
        if not rows: return
        n = len(rows)
        if n < 5: return
        o25 = sum(1 for r in rows if (r['home_goals'] or 0) + (r['away_goals'] or 0) > 2)
        btts = sum(1 for r in rows if (r['home_goals'] or 0) > 0 and (r['away_goals'] or 0) > 0)
        
        corners_over = 0
        corners_valid = 0
        for r in rows:
            if r['home_corners'] is not None and r['away_corners'] is not None:
                corners_valid += 1
                if r['home_corners'] + r['away_corners'] > 8.5:
                    corners_over += 1
                    
        scored_goals = sum(1 for r in rows if (r['home'] == team and (r['home_goals'] or 0) > 0) or (r['away'] == team and (r['away_goals'] or 0) > 0))

        if o25 / n >= 0.7:
            trends.append(f"{team} : Plus de 2.5 buts dans {int((o25/n)*100)}% de ses {n} derniers matchs")
        elif o25 / n <= 0.3:
            trends.append(f"{team} : Moins de 2.5 buts dans {int(((n-o25)/n)*100)}% de ses {n} derniers matchs")
            
        if btts / n >= 0.7:
            trends.append(f"{team} : Les deux équipes marquent (BTTS) dans {int((btts/n)*100)}% de ses matchs")
            
        if scored_goals / n >= 0.9:
            trends.append(f"{team} : A marqué au moins 1 but dans {int((scored_goals/n)*100)}% de ses matchs")
            
        if corners_valid >= 5 and (corners_over / corners_valid) >= 0.8:
            trends.append(f"{team} : Plus de 8.5 corners (total match) dans {int((corners_over/corners_valid)*100)}% de ses matchs")

    _team_trends(h_name)
    _team_trends(a_name)
    
    return trends


def _safe_rate(num, den):
    return round(num / den, 4) if den else None


def _pct_int(value):
    return int(round(value * 100)) if value is not None else None


def _team_market_profile(conn, team, limit=8):
    """Recent real team profile used to sanity-check market picks."""
    rows = conn.execute("""
        SELECT home, away, home_goals, away_goals, home_corners, away_corners,
               home_cards, away_cards
        FROM matches
        WHERE (home=? OR away=?) AND status='FINISHED' AND home_goals IS NOT NULL
        ORDER BY utc_date DESC
        LIMIT ?
    """, (team, team, limit)).fetchall()
    profile = {
        "team": team, "n": len(rows), "gfAvg": None, "gaAvg": None,
        "over25Rate": None, "bttsRate": None, "scoredRate": None,
        "concededRate": None, "cleanRate": None, "cornersAvg": None,
        "cornersOver85Rate": None, "cardsAvg": None, "cardsOver35Rate": None,
    }
    if not rows:
        return profile
    gf = ga = over25 = btts = scored = conceded = clean = 0
    corners_total = corners_over = corners_n = 0
    cards_total = cards_over = cards_n = 0
    for r in rows:
        is_home = r["home"] == team
        goals_for = r["home_goals"] if is_home else r["away_goals"]
        goals_against = r["away_goals"] if is_home else r["home_goals"]
        goals_for = goals_for or 0
        goals_against = goals_against or 0
        total_goals = (r["home_goals"] or 0) + (r["away_goals"] or 0)
        gf += goals_for
        ga += goals_against
        over25 += int(total_goals > 2)
        btts += int((r["home_goals"] or 0) > 0 and (r["away_goals"] or 0) > 0)
        scored += int(goals_for > 0)
        conceded += int(goals_against > 0)
        clean += int(goals_against == 0)
        if r["home_corners"] is not None and r["away_corners"] is not None:
            ct = (r["home_corners"] or 0) + (r["away_corners"] or 0)
            corners_total += ct
            corners_over += int(ct > 8.5)
            corners_n += 1
        if r["home_cards"] is not None and r["away_cards"] is not None:
            cd = (r["home_cards"] or 0) + (r["away_cards"] or 0)
            cards_total += cd
            cards_over += int(cd > 3.5)
            cards_n += 1
    n = len(rows)
    profile.update({
        "gfAvg": round(gf / n, 2),
        "gaAvg": round(ga / n, 2),
        "over25Rate": _safe_rate(over25, n),
        "bttsRate": _safe_rate(btts, n),
        "scoredRate": _safe_rate(scored, n),
        "concededRate": _safe_rate(conceded, n),
        "cleanRate": _safe_rate(clean, n),
        "cornersAvg": round(corners_total / corners_n, 2) if corners_n else None,
        "cornersOver85Rate": _safe_rate(corners_over, corners_n),
        "cardsAvg": round(cards_total / cards_n, 2) if cards_n else None,
        "cardsOver35Rate": _safe_rate(cards_over, cards_n),
    })
    return profile


def _avg_known(*values):
    nums = [v for v in values if isinstance(v, (int, float))]
    return sum(nums) / len(nums) if nums else None


def _market_check(market, pick, prob, verdict, impact, reason):
    return {
        "market": market,
        "pick": pick,
        "prob": round(float(prob), 4) if prob is not None else None,
        "verdict": verdict,
        "impact": impact,
        "reason": reason,
    }


def _verdict_from_impact(impact):
    if impact <= -2:
        return "avoid"
    if impact < 0:
        return "watch"
    if impact > 0:
        return "support"
    return "neutral"


def _build_market_intelligence(conn, mt, res, goals, corn, cards, confidence):
    """Explains whether team history supports or contradicts each market."""
    home, away = mt["home"], mt["away"]
    hp = _team_market_profile(conn, home)
    ap = _team_market_profile(conn, away)
    checks = []

    # 1N2 sanity check: favorite vs recent attack/defense shape.
    fav_key, fav_name, fav_prob = max(
        [("1", home, res.get("p1", 0)), ("X", "Nul", res.get("pX", 0)), ("2", away, res.get("p2", 0))],
        key=lambda x: x[2],
    )
    if fav_key != "X" and max(hp["n"], ap["n"]) >= 3:
        fav_profile = hp if fav_key == "1" else ap
        dog_profile = ap if fav_key == "1" else hp
        impact = 0
        bits = []
        if fav_profile["gfAvg"] is not None and dog_profile["gaAvg"] is not None:
            if fav_profile["gfAvg"] >= 1.8 and dog_profile["gaAvg"] >= 1.4:
                impact += 1
                bits.append(f"{fav_name} marque {fav_profile['gfAvg']} buts/m, adversaire encaisse {dog_profile['gaAvg']}")
            if fav_profile["gfAvg"] <= 1.0 and dog_profile["cleanRate"] is not None and dog_profile["cleanRate"] >= 0.45:
                impact -= 2
                bits.append(f"{fav_name} attaque peu ({fav_profile['gfAvg']} buts/m) face a une defense souvent clean")
            elif fav_profile["gfAvg"] <= 1.35 and dog_profile["cleanRate"] is not None and dog_profile["cleanRate"] >= 0.38:
                impact -= 1
                bits.append(f"favori pas assez tranchant ({fav_profile['gfAvg']} buts/m) face a une defense clean")
        draw_prob = res.get("pX", 0) or 0
        if fav_prob >= 0.62 and draw_prob >= 0.18:
            impact -= 1
            bits.append(f"nul encore dangereux ({_pct_int(draw_prob)}%) malgre le favori")
        elif fav_prob >= 0.72 and draw_prob >= 0.14:
            impact -= 1
            bits.append(f"favori fort mais nul non negligeable ({_pct_int(draw_prob)}%)")
        if (dog_profile["gaAvg"] is not None and dog_profile["gaAvg"] <= 0.9
                and dog_profile["concededRate"] is not None and dog_profile["concededRate"] <= 0.55):
            impact -= 1
            bits.append("outsider encaisse peu recemment")
        if bits:
            checks.append(_market_check("1N2", fav_name, fav_prob, _verdict_from_impact(impact), impact, "; ".join(bits)))

    # Over/Under 2.5: compare model side with both teams' recent totals.
    over_prob = goals.get("over")
    if over_prob is not None and max(hp["n"], ap["n"]) >= 3:
        pick_over = over_prob >= 0.5
        trend = _avg_known(hp["over25Rate"], ap["over25Rate"])
        impact = 0
        bits = []
        if trend is not None:
            if pick_over and trend >= 0.65:
                impact += 1; bits.append(f"historique recent Over2.5 moyen {_pct_int(trend)}%")
            elif pick_over and trend <= 0.40:
                impact -= 2; bits.append(f"historique recent plutot Under ({_pct_int(1-trend)}% Under2.5)")
            elif (not pick_over) and trend <= 0.40:
                impact += 1; bits.append(f"historique recent Under2.5 {_pct_int(1-trend)}%")
            elif (not pick_over) and trend >= 0.65:
                impact -= 2; bits.append(f"historique recent trop ouvert ({_pct_int(trend)}% Over2.5)")
        if pick_over and hp["gaAvg"] is not None and ap["gaAvg"] is not None and hp["gaAvg"] <= 0.8 and ap["gaAvg"] <= 0.8:
            impact -= 1; bits.append("deux defenses recentes solides")
        if (not pick_over) and hp["gaAvg"] is not None and ap["gaAvg"] is not None and (hp["gaAvg"] >= 1.8 or ap["gaAvg"] >= 1.8):
            impact -= 1; bits.append("au moins une defense recente fragile")
        scored_min = min(v for v in (hp["scoredRate"], ap["scoredRate"]) if v is not None) if hp["scoredRate"] is not None and ap["scoredRate"] is not None else None
        btts_signal = goals.get("btts")
        fav_prob_main = max(res.get("p1", 0) or 0, res.get("p2", 0) or 0)
        if pick_over and scored_min is not None and scored_min <= 0.55:
            impact -= 1; bits.append("une equipe marque rarement recemment")
        if pick_over and btts_signal is not None and btts_signal < 0.48 and trend is not None and trend <= 0.55:
            impact -= 1; bits.append(f"Over porte par clean sheet, BTTS modele {_pct_int(btts_signal)}%")
        if pick_over and fav_prob_main >= 0.70 and scored_min is not None and scored_min <= 0.60:
            impact -= 1; bits.append("favori fort + outsider peu buteur")
        if bits:
            checks.append(_market_check("OU", "Over 2.5" if pick_over else "Under 2.5",
                                        over_prob if pick_over else 1 - over_prob,
                                        _verdict_from_impact(impact), impact, "; ".join(bits)))

    # BTTS: compare model side with scoring/conceding rates.
    btts_prob = goals.get("btts")
    if btts_prob is not None and max(hp["n"], ap["n"]) >= 3:
        pick_yes = btts_prob >= 0.5
        trend = _avg_known(hp["bttsRate"], ap["bttsRate"])
        scored_min = min(v for v in (hp["scoredRate"], ap["scoredRate"]) if v is not None) if hp["scoredRate"] is not None and ap["scoredRate"] is not None else None
        conceded_min = min(v for v in (hp["concededRate"], ap["concededRate"]) if v is not None) if hp["concededRate"] is not None and ap["concededRate"] is not None else None
        clean_max = max(v for v in (hp["cleanRate"], ap["cleanRate"]) if v is not None) if hp["cleanRate"] is not None and ap["cleanRate"] is not None else None
        impact = 0
        bits = []
        side_prob = btts_prob if pick_yes else 1 - btts_prob
        if side_prob < 0.58:
            impact -= 2; bits.append(f"BTTS trop proche du 50/50 ({_pct_int(side_prob)}%)")
        elif side_prob < 0.63:
            impact -= 1; bits.append(f"BTTS encore serre ({_pct_int(side_prob)}%)")
        if trend is not None:
            if pick_yes and trend >= 0.65:
                impact += 1; bits.append(f"BTTS recent moyen {_pct_int(trend)}%")
            elif pick_yes and trend <= 0.45:
                impact -= 2; bits.append(f"BTTS recent faible ({_pct_int(trend)}%)")
            elif (not pick_yes) and trend <= 0.40:
                impact += 1; bits.append(f"BTTS recent faible ({_pct_int(trend)}%)")
            elif (not pick_yes) and trend >= 0.65:
                impact -= 2; bits.append(f"BTTS recent eleve ({_pct_int(trend)}%)")
        if pick_yes and scored_min is not None and scored_min <= 0.45:
            impact -= 1; bits.append("une equipe marque rarement")
        if pick_yes and clean_max is not None and clean_max >= 0.45:
            impact -= 1; bits.append("clean sheet frequent d'un cote")
        if pick_yes and conceded_min is not None and conceded_min <= 0.55:
            impact -= 1; bits.append("une equipe concede rarement")
        if (not pick_yes) and clean_max is not None and clean_max >= 0.55:
            impact += 1; bits.append("clean sheets frequents d'un cote")
        if (not pick_yes) and scored_min is not None and scored_min >= 0.80 and trend is not None and trend >= 0.55:
            impact -= 1; bits.append("deux equipes marquent souvent")
        if bits:
            checks.append(_market_check("BTTS", "BTTS Oui" if pick_yes else "BTTS Non",
                                        btts_prob if pick_yes else 1 - btts_prob,
                                        _verdict_from_impact(impact), impact, "; ".join(bits)))

    # Corners: compare model line with recent total corners.
    if corn and corn.get("line") is not None and max(hp["n"], ap["n"]) >= 3:
        line = float(corn["line"])
        pick_over = corn.get("over", 0) >= 0.5
        avg_corners = _avg_known(hp.get("cornersAvg"), ap.get("cornersAvg"))
        over85 = _avg_known(hp.get("cornersOver85Rate"), ap.get("cornersOver85Rate"))
        impact = 0
        bits = []
        if avg_corners is not None:
            if pick_over and avg_corners >= line + 1.0:
                impact += 1; bits.append(f"moyenne corners recente {avg_corners} > ligne {line}")
            elif pick_over and avg_corners <= line - 1.0:
                impact -= 2; bits.append(f"moyenne corners recente {avg_corners} sous la ligne {line}")
            elif (not pick_over) and avg_corners <= line - 0.7:
                impact += 1; bits.append(f"moyenne corners recente {avg_corners} sous la ligne {line}")
            elif (not pick_over) and avg_corners >= line + 1.0:
                impact -= 2; bits.append(f"moyenne corners recente {avg_corners} au-dessus de la ligne {line}")
        if over85 is not None and over85 >= 0.70 and not pick_over:
            impact -= 1; bits.append(f"signal historique >8.5 corners {_pct_int(over85)}%")
        if bits:
            checks.append(_market_check("CORNERS", f"Corners {'Over' if pick_over else 'Under'} {line}",
                                        corn.get("over") if pick_over else corn.get("under"),
                                        _verdict_from_impact(impact), impact, "; ".join(bits)))

    # Cards: compare model line with recent total cards.
    if cards and cards.get("line") is not None and max(hp["n"], ap["n"]) >= 3:
        line = float(cards["line"])
        pick_over = cards.get("over", 0) >= 0.5
        avg_cards = _avg_known(hp.get("cardsAvg"), ap.get("cardsAvg"))
        over35 = _avg_known(hp.get("cardsOver35Rate"), ap.get("cardsOver35Rate"))
        impact = 0
        bits = []
        if avg_cards is not None:
            if pick_over and avg_cards >= line + 0.6:
                impact += 1; bits.append(f"moyenne cartons recente {avg_cards} > ligne {line}")
            elif pick_over and avg_cards <= line - 0.6:
                impact -= 2; bits.append(f"moyenne cartons recente {avg_cards} sous la ligne {line}")
            elif (not pick_over) and avg_cards <= line - 0.5:
                impact += 1; bits.append(f"moyenne cartons recente {avg_cards} sous la ligne {line}")
            elif (not pick_over) and avg_cards >= line + 0.6:
                impact -= 2; bits.append(f"moyenne cartons recente {avg_cards} au-dessus de la ligne {line}")
        if over35 is not None and over35 >= 0.70 and not pick_over:
            impact -= 1; bits.append(f"historique >3.5 cartons {_pct_int(over35)}%")
        if bits:
            checks.append(_market_check("CARTONS", f"Cartons {'Over' if pick_over else 'Under'} {line}",
                                        cards.get("over") if pick_over else cards.get("under"),
                                        _verdict_from_impact(impact), impact, "; ".join(bits)))

    impact_total = sum(c.get("impact", 0) for c in checks)
    avoid = [c["market"] for c in checks if c["verdict"] == "avoid"]
    major_avoid = [m for m in avoid if m in ("1N2", "OU", "BTTS")]
    if major_avoid or impact_total <= -3:
        verdict = "no_bet"
        summary = "Prudence forte: un marche principal est contredit par le bilan recent des equipes."
    elif avoid or impact_total < 0:
        verdict = "watch"
        summary = "Prudence: certains marches secondaires ou signaux terrain contredisent le modele."
    elif impact_total > 0:
        verdict = "aligned"
        summary = "Bilan equipes plutot aligne avec les marches principaux."
    else:
        verdict = "neutral"
        summary = "Bilan equipes neutre ou echantillon encore limite."
    adj = max(-0.18, min(0.12, impact_total * 0.04))
    if major_avoid:
        adj = min(adj, -0.08)
    elif avoid:
        adj = min(adj, -0.03)
    return {
        "verdict": verdict,
        "summary": summary,
        "impact": impact_total,
        "confidenceAdj": round(adj, 3),
        "adjustedConfidence": round(max(0.05, min(0.98, confidence + adj)), 3),
        "noBetMarkets": sorted(set(avoid)),
        "checks": checks,
        "profiles": {"home": hp, "away": ap},
    }

def predict():
    conn = db.init_db()
    rows = conn.execute(
        "SELECT * FROM matches WHERE status IN ('SCHEDULED','LIVE','HT','FINISHED') ORDER BY utc_date").fetchall()
    ht_shares = load_halftime_shares(conn)

    # journée de poule (1/2/3) par match : Nième match de chaque équipe dans son groupe
    played_count = {}
    group_md = {}
    for r in sorted(rows, key=lambda x: x["utc_date"] or ""):
        if str(r["stage"]).startswith("Group"):
            n = max(played_count.get(r["home"], 0), played_count.get(r["away"], 0)) + 1
            group_md[r["id"]] = n
            played_count[r["home"]] = n
            played_count[r["away"]] = n

    # statut de qualification par équipe (temps réel) pour le Must-Win Index
    qual_status = stand.build_all_statuses([dict(r) for r in rows])

    # poids du modèle d'ensemble appris sur les matchs déjà joués (auto-apprentissage)
    ENS_WEIGHTS, ens_meta = _learn_ensemble(rows)
    ENS_DRAW_BIAS = ens_meta.get("drawBias", 0.0)
    ENS_TEMP = ens_meta.get("T", 1.0)   # température de calibration apprise

    # ρ/γ calibrés sur les vrais résultats (maximum de vraisemblance) ; prior sinon
    cal = calib.load()
    rho_cal = cal.get("rho", sg.DEFAULT_RHO)
    gamma_base = cal.get("gamma", 0.05)
    btts_shift = (cal.get("bttsBias") or {}).get("shift", 0.0)   # correctif empirique BTTS
    over_shift = (cal.get("overBias") or {}).get("shift", 0.0)   # correctif empirique Over 2.5
    score_calib = cal.get("scoreCalib") or {}
    score_factors = score_calib.get("factors") or {}
    bias_n = (cal.get("bttsBias") or {}).get("n", 0)
    corn_factor = (cal.get("cornersFactor") or {}).get("factor", 1.0)  # correctif corners (source biaisée)
    corn_n = (cal.get("cornersFactor") or {}).get("n", 0)
    # cotes réelles (ESPN) -> Kelly, value, line movement
    try:
        with open(os.path.join(DATA_DIR, "odds_real.json"), encoding="utf-8") as f:
            odds_store = json.load(f)
    except (OSError, ValueError):
        odds_store = {}

    try:
        with open(os.path.join(DATA_DIR, "predictions.json"), encoding="utf-8") as f:
            old_preds = {}
            for m in json.load(f):
                key = m.get("id") or f"{m.get('home')}|{m.get('away')}|{m.get('date')}"
                old_preds[key] = m
    except (OSError, ValueError):
        old_preds = {}

    out = []
    for mt in rows:
        if mt["competition"] != "CDM 2026":
            continue
        h, a = db.get_team(conn, mt["home"]), db.get_team(conn, mt["away"])
        if not h or not a:
            continue
            
        old_key = f"{mt['home']}|{mt['away']}|{mt['utc_date']}"
        old_p = old_preds.get(mt["id"]) or old_preds.get(old_key)
        # PRESERVE HISTORICAL PREDICTION to avoid look-ahead bias (changing past predictions based on new results)
        if mt["status"] in ("FINISHED", "LIVE", "HT") and old_p:
            old_p["id"] = mt["id"]
            old_p["status"] = mt["status"]
            old_p["liveScore"] = (f"{mt['home_goals']}-{mt['away_goals']}"
                                  if mt["status"] in ("LIVE", "HT") and mt["home_goals"] is not None else None)
            old_p["liveClock"] = mt["live_clock"] if mt["status"] in ("LIVE", "HT") else None
            old_p["htScore"] = (f"{mt['home_ht_goals']}-{mt['away_ht_goals']}"
                                if mt["home_ht_goals"] is not None and mt["away_ht_goals"] is not None else None)
            if mt["status"] == "FINISHED":
                old_analysis = old_p.get("analysis") or {}
                p = old_p.get("prediction", {})
                res = {"p1": p.get("p1", 0), "pX": p.get("pX", 0), "p2": p.get("p2", 0)}
                goals = {"top_score": tuple(p.get("topScore", (0, 0)))}
                analysis = _analyze_finished(mt, h, a, res, goals)
                for key in ("homeShots", "awayShots", "homeShotsOn", "awayShotsOn"):
                    if analysis.get(key) is None and old_analysis.get(key) is not None:
                        analysis[key] = old_analysis[key]
                old_p["analysis"] = analysis
                old_p["realScore"] = old_p["analysis"]["realScore"] if old_p.get("analysis") else None
                real_shots = _shots_from_analysis(old_p.get("analysis"))
                if real_shots:
                    old_p.setdefault("prediction", {})["shots"] = real_shots
            out.append(old_p)
            continue

        # Cotes 1N2 disponibles avant le calcul principal : elles servent aussi
        # de quatrième voix de calibration dans l'ensemble, avec poids plafonné.
        od = odds_store.get(f"{mt['home']}|{mt['away']}") or {}
        odd1, oddX, odd2 = od.get("odd1"), od.get("oddX"), od.get("odd2")

        lam_h = _expected_goals(h, a)
        lam_a = _expected_goals(a, h)

        # ----- forme récente réelle (10 derniers matchs) module λ -----
        fh = rform.team_form(mt["home"])
        fa = rform.team_form(mt["away"])
        if fh:
            lam_h *= (0.90 + fh["form_index"] * 0.20)   # forme 0->×0.90, forme max->×1.10
        if fa:
            lam_a *= (0.90 + fa["form_index"] * 0.20)
        lam_h, lam_a = round(max(0.2, lam_h), 2), round(max(0.2, lam_a), 2)

        # ----- impact de la composition (3 angles) -----
        # formations : réelles si match fini, sinon défaut (4-3-3 / selon l'adversaire)
        lu = None
        try:
            if mt["events_json"]:
                lu = (json.loads(mt["events_json"]) or {}).get("lineups")
        except (KeyError, TypeError, ValueError):
            lu = None
        projected_lu = None if lu else _projected_lineup(mt["home"], mt["away"])
        lineup_src = lu or projected_lu or {}
        hform = lineup_src.get("home_formation", "4-3-3")
        aform = lineup_src.get("away_formation", "4-4-2")
        
        def _extract_pos(players_list, fallback_form=None):
            out = []
            for p in (players_list or []):
                mm = re.search(r"\(([A-Z]+)\)", str(p or ""))
                if mm:
                    out.append(mm.group(1))
            if out:
                return out
            if players_list and fallback_form:
                return li.formation_positions(fallback_form)
            return out

        if lineup_src.get("home_xi"):
            hpos = _extract_pos(lineup_src.get("home_xi"), hform)
        else:
            hpos = li.formation_positions(hform)

        if lineup_src.get("away_xi"):
            apos = _extract_pos(lineup_src.get("away_xi"), aform)
        else:
            apos = li.formation_positions(aform)

        hbench = _extract_pos(lineup_src.get("home_bench"))
        abench = _extract_pos(lineup_src.get("away_bench"))
        lam_h, lam_a, lineup_info = li.apply_lineup(
            lam_h, lam_a, hpos, apos, hform, aform,
            home_bench=hbench, away_bench=abench,
            home_elo=h["elo"], away_elo=a["elo"])
        
        # Les vraies absences clés sont calculées plus bas par availability_factor().
        # On ne transforme pas un delta de formation en "joueur manquant".

        # ANGLE 1 — Must-Win Index : enjeu + statut de qualification réel (théorie des jeux)
        md = group_md.get(mt["id"])
        stage_for_mwi = f"Matchday {md}" if md else mt["stage"]   # "Matchday 3" = enjeu max
        sh = qual_status.get(mt["home"])
        sa = qual_status.get(mt["away"])
        # qualifié -> lève le pied (True) ; éliminé -> plus rien à jouer (True aussi = démotivé)
        q_home = True if sh in ("qualified", "eliminated") else (False if sh == "alive" and md == 3 else None)
        q_away = True if sa in ("qualified", "eliminated") else (False if sa == "alive" and md == 3 else None)
        mwi = ctx.must_win_index(stage_for_mwi, q_home, q_away)
        mwi["groupMatchday"] = md
        mwi["statusHome"] = sh
        mwi["statusAway"] = sa
        lam_h, lam_a = ctx.apply_mwi(lam_h, lam_a, mwi)

        # ----- FINITION : régression vers la moyenne (buts vs xG) -----
        # un favori qui surperformait sa finition est ramené à la réalité, etc.
        fin_h, ratio_h = upset_mod.finishing_factor(h["gf_avg"], h["xg_avg"], h["matches_played"])
        fin_a, ratio_a = upset_mod.finishing_factor(a["gf_avg"], a["xg_avg"], a["matches_played"])
        lam_h = round(max(0.2, lam_h * fin_h), 2)
        lam_a = round(max(0.2, lam_a * fin_a), 2)

        # ----- QUALITÉ OFFENSIVE ET DÉFENSIVE INDIVIDUELLE (EA FC) -----
        # corrige la sous-estimation des équipes sans match CDM joué en s'appuyant sur les traits EA FC.
        _sq = _load_squads()
        atk_h = atkq.attack_rating(_sq.get(mt["home"]))
        atk_a = atkq.attack_rating(_sq.get(mt["away"]))
        def_h = defq.defense_rating(_sq.get(mt["home"]))
        def_a = defq.defense_rating(_sq.get(mt["away"]))
        
        # Le lambda (xG) est boosté par sa propre attaque, et réduit par la défense adverse.
        lam_h = round(lam_h * atk_h["boost"] * def_a["shield"], 2)
        lam_a = round(lam_a * atk_a["boost"] * def_h["shield"], 2)

        # ----- DISPONIBILITÉ DE L'EFFECTIF (absences = λ réduit) -----
        # N'agit QUE si l'on dispose du XI RÉEL (officiel/probable ESPN), sinon 1.0.
        # Corrige l'Elo "artificiellement haut" quand un joueur clé manque.
        # uniquement pour les matchs NON joués : sur un match fini le résultat est
        # connu, le malus n'a pas de sens et fausserait la comparaison prono↔réel.
        if mt["status"] == "FINISHED":
            avh = {"factor": 1.0, "missing": [], "applied": False}
            ava = {"factor": 1.0, "missing": [], "applied": False}
        else:
            _pstats_av = _load_player_stats()
            _xi_h = (lu or {}).get("home_xi")
            _xi_a = (lu or {}).get("away_xi")
            avh = avail.availability_factor(_sq.get(mt["home"]), _xi_h, _pstats_av.get(mt["home"]))
            ava = avail.availability_factor(_sq.get(mt["away"]), _xi_a, _pstats_av.get(mt["away"]))
            lam_h = round(max(0.2, lam_h * avh["factor"]), 2)
            lam_a = round(max(0.2, lam_a * ava["factor"]), 2)

        # ----- NLP MOMENTUM (Live/HT uniquement) -----
        # Analyse le commentaire ESPN en temps réel et ajuste λ selon la dynamique du match.
        nlp_signal = None
        if mt["status"] in ("LIVE", "HT"):
            try:
                from collector.sources import espn_stats as _espn
                _ev = _espn.find_event(mt["home"], mt["away"])
                if _ev:
                    _tl = _espn.get_timeline(_ev["id"])
                    _comments = _tl.get("commentary", [])
                    # Extraire la minute courante depuis live_clock (ex: '67\'' -> 67)
                    _min_raw = mt["live_clock"] or "0"
                    _min_match = re.search(r"(\d+)", str(_min_raw))
                    _cur_min = int(_min_match.group(1)) if _min_match else 0
                    _sig = nlpm.analyse_commentary(
                        _comments, mt["home"], mt["away"],
                        current_minute=_cur_min, window_size=20
                    )
                    _pen = nlpm.extract_live_penalties(_comments, mt["home"], mt["away"])
                    
                    # Appliquer d'abord la pénalité structurelle
                    lam_h = lam_h * _pen.home_penalty_adj
                    lam_a = lam_a * _pen.away_penalty_adj
                    
                    # Appliquer les multiplicateurs λ (effet NLP plafonné à ±20%)
                    _nlp_h = max(0.80, min(1.20, _sig.home_lambda_adj))
                    _nlp_a = max(0.80, min(1.20, _sig.away_lambda_adj))
                    lam_h = round(max(0.2, lam_h * _nlp_h), 2)
                    lam_a = round(max(0.2, lam_a * _nlp_a), 2)
                    
                    nlp_signal = nlpm.momentum_to_dict(_sig)
                    nlp_signal['penalties'] = {
                        'home_adj': _pen.home_penalty_adj,
                        'away_adj': _pen.away_penalty_adj,
                        'home_reasons': _pen.home_reasons,
                        'away_reasons': _pen.away_reasons
                    }
            except Exception as _nlp_err:
                import traceback as _tb
                print(f"[NLP] ERREUR sur {mt['home']} vs {mt['away']}: {_nlp_err}", flush=True)
                _tb.print_exc()
                nlp_signal = None

        # ----- grille de scores CORRIGÉE (Dixon-Coles + effet de choc bivarié) -----
        # Dynamically adjust rho based on combined defensive strength
        h_xga = h["xga_avg"] if "xga_avg" in h.keys() else 1.2
        a_xga = a["xga_avg"] if "xga_avg" in a.keys() else 1.2
        xga_avg_comb = (h_xga + a_xga) / 2.0
        dyn_rho = max(-0.15, min(-0.02, -0.15 + (xga_avg_comb - 0.8) * (0.13 / 0.7))) if rho_cal == sg.DEFAULT_RHO else rho_cal
        
        # Dynamically adjust gamma based on match openness
        h_xg = h["xg_avg"] if "xg_avg" in h.keys() else 1.2
        a_xg = a["xg_avg"] if "xg_avg" in a.keys() else 1.2
        xg_avg_comb = (h_xg + a_xg) / 2.0
        openness = (xg_avg_comb + xga_avg_comb) / 2.0
        gamma_bonus = max(0.0, min(0.10, (openness - 1.2) * 0.15))
        
        gamma = round(min(0.25, gamma_base + gamma_bonus + sg.shock_gamma(h["elo"] - a["elo"], mwi["stageStake"])), 3)
        raw_grid = sg.score_grid(lam_h, lam_a, rho=dyn_rho, gamma=gamma)
        grid = sg.apply_score_factors(raw_grid, score_factors)

        res = markets.result_model(h["elo"], a["elo"], lam_h, lam_a, grid=grid)

        # ===== MODÈLE D'ENSEMBLE 1N2 (Elo + grille + forme + marché) =====
        # 4 sous-modèles indépendants votent ; poids = perf réelle mesurée (auto-apprentissage).
        _go = sg.outcomes(grid)
        grid_p = (_go["p1"], _go["pX"], _go["p2"])
        elo_p = ens.elo_probs(h["elo"], a["elo"])
        form_p = ens.form_probs(fh["form_index"] if fh else 0.5,
                                fa["form_index"] if fa else 0.5)
        market_p = ens.market_probs(odd1, oddX, odd2)
        _ensr = ens.combine(elo_p, grid_p, form_p, market_p=market_p, weights=ENS_WEIGHTS,
                            elo_d=h["elo"] - a["elo"])
        # calibration par température (corrige la sur-confiance mesurée)
        _c1, _cx, _c2 = ens.apply_temperature(_ensr["p1"], _ensr["pX"], _ensr["p2"], ENS_TEMP)
        _c1, _cx, _c2 = ens.apply_draw_bias(_c1, _cx, _c2, ENS_DRAW_BIAS)
        res["p1"], res["pX"], res["p2"] = round(_c1, 4), round(_cx, 4), round(_c2, 4)
        res["ensemble"] = {"weights": ENS_WEIGHTS, "T": ENS_TEMP, "drawBias": ENS_DRAW_BIAS,
                           "elo": [round(x, 3) for x in elo_p],
                           "grid": [round(x, 3) for x in grid_p],
                           "form": [round(x, 3) for x in form_p]}
        if market_p:
            res["ensemble"]["market"] = [round(x, 3) for x in market_p]

        goals = markets.goals_model(lam_h, lam_a, grid=grid)
        # marchés dérivés (Double Chance, Draw No Bet, top-3 scores) + scénarios narratifs
        # — TOUT est dérivé de la grille corrigée, aucune donnée externe/inventée
        derived = sg.derived_markets(grid)
        scenarios = sg.scenarios(grid)
        # Over/Under multi-lignes + score mi-temps (tout dérivé de la grille corrigée)
        ou_lines = sg.over_under_lines(grid)
        share_h = ht_shares.get(mt["home"], 0.42)
        share_a = ht_shares.get(mt["away"], 0.42)
        ht = sg.halftime(lam_h, lam_a, rho=rho_cal, gamma=gamma, share_h=share_h, share_a=share_a)
        # bonus Over 2.5 lié à la profondeur de banc (fin de match)
        goals["over"] = round(min(0.98, goals["over"] + lineup_info["benchBonusOver25"]), 4)
        # correctifs empiriques (biais systématique mesuré sur les matchs joués) —
        # bornés [0.02, 0.98], fortement réduits par shrinkage tant que peu de matchs
        btts_raw = goals["btts"]
        goals["btts"] = round(max(0.02, min(0.98, goals["btts"] + btts_shift)), 4)
        goals["over"] = round(max(0.02, min(0.98, goals["over"] + over_shift)), 4)
        # facteurs de domination calculés plus tôt pour les corners et tirs
        lam_tot = max(lam_h + lam_a, 0.5)
        dom_h = 0.5 + (lam_h / lam_tot)
        dom_a = 0.5 + (lam_a / lam_tot)
        elo_f = 10 ** ((h["elo"] - a["elo"]) / 1600.0)
        dom_h = max(0.82, min(1.22, dom_h * elo_f))
        dom_a = max(0.82, min(1.22, dom_a / elo_f))

        # corners : prior FootyStats × facteur correctif empirique (source surestime ~×1.67)
        ch = shr.shrink(h["corners_avg"], h["matches_played"], setp.get_corners(mt["home"]) or PRIOR["corners"]) * corn_factor
        ca = shr.shrink(a["corners_avg"], a["matches_played"], setp.get_corners(mt["away"]) or PRIOR["corners"]) * corn_factor
        corn = markets.corners_model(ch, ca, dom_h=dom_h, dom_a=dom_a)
        card_h = shr.shrink(h["cards_avg"], h["matches_played"], setp.get_cards(mt["home"]) or PRIOR["cards"])
        card_a = shr.shrink(a["cards_avg"], a["matches_played"], setp.get_cards(mt["away"]) or PRIOR["cards"])
        # ----- STYLE D'ARBITRAGE : module les cartons selon la sévérité de l'arbitre -----
        referee = refs.get_referee(mt["home"], mt["away"])
        # fallback : arbitre RÉEL ESPN (match joué) si pas de désignation pré-match
        if not referee or not (referee or {}).get("name"):
            _rr = _real_referee(mt["home"], mt["away"])
            if _rr:
                referee = {"name": _rr, "nation": None, "cardsAvg": None,
                           "source": "ESPN (réel)"}
        ref_name = (referee or {}).get("name") if referee else None
        ref_sev = refform.severity(ref_name) if ref_name else None
        team_cards = card_h + card_a       # cartons attendus selon les équipes
        if ref_sev and ref_sev["avg"]:
            # combine 50% style équipes + 50% style arbitre (sévérité = cartons/match)
            blended = 0.5 * team_cards + 0.5 * ref_sev["avg"]
            scale = blended / max(team_cards, 0.5)
            card_h *= scale; card_a *= scale
        cards = markets.cards_model(card_h, card_a)
        
        if "fouls_avg" in h.keys() and h["fouls_avg"] is not None:
            cards["foulsHome"] = round(h["fouls_avg"], 1)
        if "fouls_avg" in a.keys() and a["fouls_avg"] is not None:
            cards["foulsAway"] = round(a["fouls_avg"], 1)

        # source du prior corners/cartons (réel FootyStats vs générique)
        _real_sp = setp.get_corners(mt["home"]) is not None and setp.get_corners(mt["away"]) is not None
        corn["src"] = ("FootyStats ×%.2f (calibré %d matchs)" % (corn_factor, corn_n)) if (_real_sp and corn_n) else \
                      ("FootyStats (10 derniers, réel)" if _real_sp else "prior générique")
        cards["src"] = "FootyStats + arbitre" if ref_sev else ("FootyStats (réel)" if _real_sp else "prior générique")
        if ref_sev:
            cards["refSeverity"] = ref_sev
        if referee and ref_sev:
            referee = {**referee, "severity": ref_sev["avg"], "severityN": ref_sev["n"],
                       "severitySrc": ref_sev["source"]}
        risk = {"home": _risk_players(mt["home"]), "away": _risk_players(mt["away"])}
        # pronos JOUEURS (6 rôles) en probabilités — effectif réel + production réelle
        squads = _load_squads()
        pstats = _load_player_stats()
        home_xi = lineup_src.get("home_xi")
        away_xi = lineup_src.get("away_xi")
        squad_home_key = _team_data_key(mt["home"], squads)
        squad_away_key = _team_data_key(mt["away"], squads)
        stats_home_key = _team_data_key(mt["home"], pstats)
        stats_away_key = _team_data_key(mt["away"], pstats)
        player_props = {
            "home": pprops.compute(mt["home"], squads.get(squad_home_key), lam_h, lam_a,
                                   stats_team=pstats.get(stats_home_key), lineup_xi=home_xi),
            "away": pprops.compute(mt["away"], squads.get(squad_away_key), lam_a, lam_h,
                                   stats_team=pstats.get(stats_away_key), lineup_xi=away_xi),
        }
        # attache la bio RÉELLE (forces/faiblesses) aux joueurs clés cités
        for side in ("home", "away"):
            _attach_bios(player_props.get(side))
        # TIRS — données RÉELLES par équipe (matchs joués). Pas d'estimation pour les
        # matchs à venir : aucune source gratuite ne donne les tirs/match par sélection.
        def _acc(s, sot):
            return round(sot / s * 100) if (s and sot is not None and s > 0) else None
        if mt["status"] == "FINISHED" and mt["home_shots"] is not None:
            # match joué : on affiche les TIRS RÉELS (ESPN)
            shots = {
                "home": mt["home_shots"], "away": mt["away_shots"],
                "homeOn": mt["home_shots_on"], "awayOn": mt["away_shots_on"],
                "homeAcc": _acc(mt["home_shots"], mt["home_shots_on"]),
                "awayAcc": _acc(mt["away_shots"], mt["away_shots_on"]),
                "real": True,
            }
        else:
            # ===== PRONO TIRS/CADRÉS — modèle multi-facteurs (refonte) =====
            # Basé sur 4 piliers RÉELS (corrélations mesurées sur les matchs joués) :
            #   1) attaque/défense : tirs produits par l'équipe × tirs concédés par l'adversaire
            #   2) DOMINATION : modulé par λ (buts attendus) et écart Elo (r≈0.68 vs tirs)
            #   3) POSSESSION : une équipe qui tient le ballon tire plus (r≈0.66)
            #   4) PRÉCISION par équipe : cadrés = tirs × taux de mise au cadre propre (8→73%)
            nh, na = h["matches_played"], a["matches_played"]
            # 1) base attaque/défense
            base_h = (shr.shrink(h["shots_avg"], nh, PRIOR["shots"])
                      + shr.shrink(a["shots_against_avg"], na, PRIOR["shots"])) / 2
            base_a = (shr.shrink(a["shots_avg"], na, PRIOR["shots"])
                      + shr.shrink(h["shots_against_avg"], nh, PRIOR["shots"])) / 2
            # 2) facteur domination = calculé plus haut
            # 3) facteur possession (centré sur 50%), borné [0.85, 1.18]
            ph = shr.shrink(h["possession_avg"] if "possession_avg" in h.keys() else 50.0, nh, PRIOR["possession"])
            pa = shr.shrink(a["possession_avg"] if "possession_avg" in a.keys() else 50.0, na, PRIOR["possession"])
            # normalise pour que la somme reste ~100
            psum = max(ph + pa, 1.0)
            ph, pa = ph / psum * 100, pa / psum * 100
            poss_h = max(0.85, min(1.18, 0.6 + ph / 125.0))
            poss_a = max(0.85, min(1.18, 0.6 + pa / 125.0))
            # combinaison (domination + possession appliquées à mi-poids chacune)
            sh_h = base_h * (0.5 * dom_h + 0.5 * poss_h)
            sh_a = base_a * (0.5 * dom_a + 0.5 * poss_a)
            # 4) précision propre à chaque équipe (cadrés/tirs), shrinkée vers 34%
            acc_h = shr.shrink(_team_accuracy(h), nh, PRIOR["accuracy"])
            acc_a = shr.shrink(_team_accuracy(a), na, PRIOR["accuracy"])
            son_h = sh_h * acc_h
            son_a = sh_a * acc_a
            sm = markets.shots_model(sh_h, sh_a, son_h, son_a)
            sm["real"] = False
            sm["basis"] = {"dominance": [round(dom_h, 2), round(dom_a, 2)],
                           "possession": [round(ph), round(pa)],
                           "accuracy": [round(acc_h * 100), round(acc_a * 100)]}
            if "shots_avg" in h.keys() and h["shots_avg"] is not None:
                sm["shotsAvgHome"] = round(h["shots_avg"], 1)
            if "shots_avg" in a.keys() and a["shots_avg"] is not None:
                sm["shotsAvgAway"] = round(a["shots_avg"], 1)
            shots = sm

        # ANGLE 2 — métacognition : le modèle s'auto-évalue (confiance + raisons)
        meta = ctx.model_confidence(
            fh, fa, h["matches_played"], a["matches_played"],
            form_real_home=bool(fh), form_real_away=bool(fa))
        base_conf = meta["confidence"]
        market_intel = _build_market_intelligence(conn, mt, res, goals, corn, cards, base_conf)
        conf = market_intel["adjustedConfidence"]
        meta["baseConfidence"] = round(base_conf, 3)
        meta["marketAdjustedConfidence"] = conf

        # ----- INDICE DE SURPRISE (au-delà des maths) -----
        # qui est favori ? signaux : bloc bas de l'outsider, favori en surperformance, rouge, serrement
        fav_is_home = res["p1"] >= res["p2"]
        p_fav = max(res["p1"], res["p2"]); p_dog = min(res["p1"], res["p2"])
        dog = a if fav_is_home else h
        fav = h if fav_is_home else a
        # bloc bas outsider : encaisse peu d'xG (défense solide) — vrai si xga_avg bas et a joué
        dog_low_block = (dog["matches_played"] > 0 and dog["xga_avg"] < 1.1)
        # favori en surperformance de finition (ratio buts/xG > 1.15)
        fav_ratio = (ratio_h if fav_is_home else ratio_a)
        fav_overperf = bool(fav_ratio and fav_ratio > 1.15)
        # outsider qui n'a besoin que d'un nul (statut qualif / MWI faible)
        dog_needs_draw = ((mwi.get("statusAway") if fav_is_home else mwi.get("statusHome")) == "qualified")
        ui = upset_mod.upset_index(p_fav, p_dog, fav, dog_low_block, fav_overperf,
                                   cards.get("redProb"), dog_needs_draw)
        # atténuation prudente de la domination du favori si surprise probable
        damp = upset_mod.context_dampener(ui["index"])
        if damp < 1.0:
            if fav_is_home:
                shift = res["p1"] * (1 - damp); res["p1"] = round(res["p1"] - shift, 4)
            else:
                shift = res["p2"] * (1 - damp); res["p2"] = round(res["p2"] - shift, 4)
            res["pX"] = round(res["pX"] + shift, 4)   # redistribué vers le nul
        ui["dampener"] = damp
        ui["favOverperf"] = fav_overperf
        ui["dogLowBlock"] = dog_low_block

        # ----- COTES réelles -> value, Kelly, line movement -----
        
        def _value(p, o, market="1N2"):
            if not p or not o or o <= 1: return None
            implied = 1 / o
            edge = p - implied
            min_edge = VALUE_EDGE_MIN.get(market, 0.15)
            return {"odd": o, "implied": round(implied, 3), "edge": round(edge, 3),
                    "minEdge": min_edge, "is_value": edge >= min_edge}

        value = {"home": _value(res["p1"], odd1, "1N2"), "draw": _value(res["pX"], oddX, "1N2"),
                 "away": _value(res["p2"], odd2, "1N2")}
                 
        ou_line = od.get("ou_line")
        odd_over = od.get("over")
        odd_under = od.get("under")
        if ou_line is not None and odd_over and odd_under:
            ou_str = str(ou_line)
            if "ou_lines" in res and ou_str in res["ou_lines"]:
                value["over"] = _value(res["ou_lines"][ou_str]["over"], odd_over, "OU")
                value["under"] = _value(res["ou_lines"][ou_str]["under"], odd_under, "OU")
                
        # Smarkets odds extraction
        oddBTTS_Yes = od.get("oddBTTS_Yes")
        oddBTTS_No = od.get("oddBTTS_No")
        if oddBTTS_Yes and goals.get("btts"):
            value["btts_yes"] = _value(goals["btts"], oddBTTS_Yes, "BTTS")
        if oddBTTS_No and goals.get("btts"):
            value["btts_no"] = _value(1 - goals["btts"], oddBTTS_No, "BTTS")
            
        oddCorners_line = od.get("oddCorners_line")
        oddCorners_Over = od.get("oddCorners_Over")
        oddCorners_Under = od.get("oddCorners_Under")
        if oddCorners_line and oddCorners_Over and res.get("corners", {}).get("total_mean"):
            # Very simplistic edge calculation for corners: use Poisson CDF to estimate proba
            import math
            def poisson_cdf(mu, k):
                return sum(math.exp(-mu) * (mu**i) / math.factorial(i) for i in range(int(k)+1))
            
            p_under = poisson_cdf(res["corners"]["total_mean"], math.floor(oddCorners_line))
            p_over = 1 - p_under
            value["corners_over"] = _value(p_over, oddCorners_Over, "CORNERS")
            if oddCorners_Under:
                value["corners_under"] = _value(p_under, oddCorners_Under, "CORNERS")

        kelly = {"home": ctx.kelly_fraction(res["p1"], odd1, conf),
                 "draw": ctx.kelly_fraction(res["pX"], oddX, conf),
                 "away": ctx.kelly_fraction(res["p2"], odd2, conf)}

        op = od.get("opening")
        line_move = None
        if op and odd1 and op.get("odd1"):
            line_move = {"home": round(odd1 - op["odd1"], 3),
                         "draw": round((oddX or 0) - (op.get("oddX") or 0), 3),
                         "away": round((odd2 or 0) - (op.get("odd2") or 0), 3),
                         "opening": op, "provider": od.get("provider")}

        live_score = (f"{mt['home_goals']}-{mt['away_goals']}"
                      if mt["status"] in ("LIVE", "HT") and mt["home_goals"] is not None
                      else None)
        live_clock = mt["live_clock"] if ("live_clock" in mt.keys() and mt["status"] in ("LIVE", "HT")) else None
        
        ht_score = (f"{mt['home_ht_goals']}-{mt['away_ht_goals']}"
                    if "home_ht_goals" in mt.keys() and mt["home_ht_goals"] is not None and mt["away_ht_goals"] is not None
                    else None)

        analysis = _analyze_finished(mt, h, a, res, goals) if mt["status"] == "FINISHED" else None
        trends = _calculate_trends(conn, h["name"], a["name"])
        official_lineups = None
        if lu and ((lu.get("home_xi") or []) or (lu.get("away_xi") or [])):
            official_lineups = {
                "source": lu.get("source_xi") or lu.get("source") or "ESPN",
                "homeFormation": lu.get("home_formation"),
                "awayFormation": lu.get("away_formation"),
                "homeXi": lu.get("home_xi") or [],
                "awayXi": lu.get("away_xi") or [],
                "homeBench": lu.get("home_bench") or [],
                "awayBench": lu.get("away_bench") or [],
            }
        projected_lineups = None
        if (not official_lineups) and projected_lu and ((projected_lu.get("home_xi") or []) or (projected_lu.get("away_xi") or [])):
            projected_lineups = {
                "source": projected_lu.get("source") or "Projected lineup",
                "url": projected_lu.get("url"),
                "homeFormation": projected_lu.get("home_formation"),
                "awayFormation": projected_lu.get("away_formation"),
                "homeXi": projected_lu.get("home_xi") or [],
                "awayXi": projected_lu.get("away_xi") or [],
                "homeBench": projected_lu.get("home_bench") or [],
                "awayBench": projected_lu.get("away_bench") or [],
            }
        source_tags = ["free-mode", "openfootball", "SQLite", "Elo", "shrinkage", "FIFA-ratings"] + (["ESPN-free-odds", "market-implied-model"] if odd1 else []) + (["Smarkets-free-odds"] if oddBTTS_Yes else [])
        if projected_lineups:
            source_tags.append("FotMob-projected-XI")
        out.append({
            "id": mt["id"],
            "league": f"CDM 2026 · {mt['stage']}",
            "date": mt["utc_date"],
            "status": mt["status"],
            "liveScore": live_score,
            "liveClock": live_clock,
            "realScore": analysis["realScore"] if analysis else None,
            "htScore": ht_score,
            "analysis": analysis,
            "nlpMomentum": nlp_signal,
            "hotTrends": trends,
            "home": mt["home"], "away": mt["away"],
            "homeGF": round(h["gf_avg"], 2), "awayGF": round(a["gf_avg"], 2),
            "homeGA": round(h["ga_avg"], 2), "awayGA": round(a["ga_avg"], 2),
            "homeXG": round(lam_h, 2), "awayXG": round(lam_a, 2),
            "homeForm": 8, "awayForm": 8,
            "homeElo": h["elo"], "awayElo": a["elo"],
            "homeForm5": (fh or {}).get("last5"), "awayForm5": (fa or {}).get("last5"),
            "homeFormDetail": fh, "awayFormDetail": fa,
            "odd1": odd1, "oddX": oddX, "odd2": odd2, 
            "oddOU_line": ou_line, "oddOver": odd_over, "oddUnder": odd_under,
            "oddBTTS_Yes": oddBTTS_Yes, "oddBTTS_No": oddBTTS_No,
            "oddCorners_line": oddCorners_line, "oddCorners_Over": oddCorners_Over, "oddCorners_Under": oddCorners_Under,
            "oddCards_line": od.get("oddCards_line"), "oddCards_Over": od.get("oddCards_Over"), "oddCards_Under": od.get("oddCards_Under"),
            "oddsProvider": od.get("provider"),
            "sources": source_tags,
            "confidence": round(conf, 2),
            "prediction": {
                "p1": res["p1"], "pX": res["pX"], "p2": res["p2"],
                "ensemble": res.get("ensemble"),
                # Cohérence : si le score modal est un clean sheet, le BTTS ne doit pas être "Oui" (>0.5)
                "over25": goals["over"], 
                "btts": goals["btts"],
                "marketCalib": {"bttsShift": btts_shift, "overShift": over_shift,
                                "bttsRaw": round(btts_raw, 4), "n": bias_n},
                "lamHome": lam_h, "lamAway": lam_a,
                "topScore": list(goals["top_score"]),
                # marchés dérivés + scénarios (100% issus de la grille de scores réelle)
                "doubleChance": derived["doubleChance"],
                "drawNoBet": derived["drawNoBet"],
                "topScores": derived["topScores"],
                "scenarios": scenarios,
                # buts : Over/Under multi-lignes, total xG projeté, BTTS+confiance, score mi-temps
                "overUnder": ou_lines,
                "totalXg": round(lam_h + lam_a, 2),
                "bttsConf": _btts_confidence(goals["btts"], conf),
                "halftime": ht,
                "value": value,
                "corners": corn, "cards": cards, "shots": shots,
                "marketIntelligence": market_intel,
                "referee": referee, "riskPlayers": risk,
                "playerProps": player_props,
                "lineupImpact": lineup_info,
                "formations": {"home": hform, "away": aform},
                "officialLineups": official_lineups,
                "projectedLineups": projected_lineups,
                # intelligence contextuelle (3 angles)
                "mwi": mwi,
                "meta": meta,
                "upsetIndex": ui,
                "attackQuality": {"home": atk_h, "away": atk_a},
                "defenseQuality": {"home": def_h, "away": def_a},
                "availability": {"home": avh, "away": ava},
                "kelly": kelly,         # calculé avec les vraies cotes ESPN
                "lineMovement": line_move,
                "dixonColes": {"rho": rho_cal, "gamma": gamma,
                               "calibratedOn": cal.get("n_matches", 0),
                               "scoreCalibratedOn": score_calib.get("n", 0)},
                # marché "qui se qualifie ?" (uniquement en phase à élimination directe)
                "knockout": (ko.qualification(lam_h, lam_a, h["elo"], a["elo"],
                                              gamma=gamma, form_h=fh, form_a=fa)
                             if not str(mt["stage"]).startswith("Group") else None),
            },
        })
    out = [_normalize_source_tags(m) for m in out]
    conn.close()
    path = os.path.join(DATA_DIR, "predictions.json")
    import time
    for _ in range(5):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
            break
        except OSError:
            time.sleep(0.1)
    print(f"✅ predict : {len(out)} pronostics (4 modèles) -> {path}")

    # ----- SÉLECTION DES MEILLEURS CHOIX ("Top Picks") -----
    # filtre tout ce que l'app prédit pour ne garder que les paris les plus sûrs,
    # avec le taux de réussite RÉELLEMENT mesuré sur les matchs joués.
    try:
        from collector.models import best_picks as bpk
        tp = bpk.build_top_picks(out, max_picks=20)
        tp_path = os.path.join(DATA_DIR, "top_picks.json")
        with open(tp_path, "w", encoding="utf-8") as f:
            json.dump(tp, f, ensure_ascii=False, indent=2)
        rel = tp["reliability"]["byTier"]["lock"]
        print(f"✅ top picks : {tp['lockCount']} verrouillés "
              f"(fiabilité 🔒 mesurée : {rel['pct']}% sur {rel['total']} cas) -> {tp_path}")
              
        from collector.models import combo
        cdata = combo.update_daily_combo(tp, out)
        print(f"✅ combiné du jour : {cdata['stats']['won']}W - {cdata['stats']['lost']}L - {cdata['stats']['pending']}P")
    except Exception as e:
        print(f"   [warn] top picks / combo non générés : {e}")

    # ----- PnL / ROI (Yield) — la métrique reine -----
    try:
        from collector.models import pnl as pnlmod
        pn = pnlmod.build_pnl(out)
        with open(os.path.join(DATA_DIR, "pnl.json"), "w", encoding="utf-8") as f:
            json.dump(pn, f, ensure_ascii=False, indent=2)
        v = pn["value"]
        print(f"✅ PnL/ROI : value {v['pnl']:+.2f}u (yield {v['yield']}%, {v['bets']} paris) "
              f"· {len(pn['topValue'])} value bets du jour")
    except Exception as e:
        print(f"   [warn] PnL non généré : {e}")

    # ----- CLASSEMENT DES GROUPES (standings) -----
    try:
        _ms = [{"home": m["home"], "away": m["away"],
                "stage": m["league"].replace("CDM 2026 · ", ""),
                "status": m["status"],
                "home_goals": int(m["realScore"].split("-")[0]) if m.get("realScore") else None,
                "away_goals": int(m["realScore"].split("-")[1]) if m.get("realScore") else None}
               for m in out]
        standings = stand.build_standings(_ms)
        with open(os.path.join(DATA_DIR, "standings.json"), "w", encoding="utf-8") as f:
            json.dump(standings, f, ensure_ascii=False, indent=2)
        print(f"✅ standings : {len(standings)} groupes classés")
    except Exception as e:
        print(f"   [warn] standings non généré : {e}")


def main():
    ap = argparse.ArgumentParser(description="Pipeline ProноFoot (système évolutif)")
    ap.add_argument("cmd", choices=["seed", "ingest", "update", "predict", "run", "ratings"])
    args = ap.parse_args()
    if args.cmd == "seed": seed()
    elif args.cmd == "ingest": ingest()
    elif args.cmd == "update": update()
    elif args.cmd == "predict": predict()
    elif args.cmd == "run":
        ingest(); update(); predict()
    elif args.cmd == "ratings":
        conn = db.init_db()
        print(f"{'ÉQUIPE':24} {'ELO':>7} {'J':>3} {'GF':>5} {'GA':>5}")
        for t in db.all_teams(conn)[:20]:
            print(f"{t['name']:24} {t['elo']:7.0f} {t['matches_played']:3} "
                  f"{t['gf_avg']:5.2f} {t['ga_avg']:5.2f}")
        conn.close()


if __name__ == "__main__":
    main()

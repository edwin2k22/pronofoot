"""
Classements de groupe en temps réel + statut de qualification (pour le MWI).

À partir des matchs terminés, calcule pour chaque groupe : points, diff de buts,
buts marqués, puis détermine le STATUT de chaque équipe avant un match donné :
  - "qualified"  : mathématiquement qualifiée pour les 1/16 (top 2 assuré)
  - "eliminated" : ne peut plus se qualifier
  - "alive"      : tout reste possible (doit jouer)

Format CDM 2026 : 12 groupes de 4, les 2 premiers + 8 meilleurs 3es passent.
On reste prudent : on ne déclare "qualified/eliminated" que si c'est certain
après 2 journées ; sinon "alive". Ce statut alimente le Must-Win Index.
"""
from __future__ import annotations


def _result_points(gf, ga):
    return 3 if gf > ga else 1 if gf == ga else 0


def compute_group_table(matches: list[dict]) -> dict[str, dict]:
    """
    matches : liste de dicts {home, away, home_goals, away_goals, status, stage}
    Renvoie {team: {pts, gd, gf, played}} pour les matchs FINISHED d'un groupe.
    """
    table: dict[str, dict] = {}
    for m in matches:
        if m["status"] != "FINISHED" or m["home_goals"] is None:
            continue
        h, a = m["home"], m["away"]
        hg, ag = m["home_goals"], m["away_goals"]
        for t in (h, a):
            table.setdefault(t, {"pts": 0, "gd": 0, "gf": 0, "played": 0})
        table[h]["pts"] += _result_points(hg, ag)
        table[a]["pts"] += _result_points(ag, hg)
        table[h]["gd"] += hg - ag; table[a]["gd"] += ag - hg
        table[h]["gf"] += hg; table[a]["gf"] += ag
        table[h]["played"] += 1; table[a]["played"] += 1
    return table


def _rank(table: dict) -> list[tuple[str, dict]]:
    return sorted(table.items(),
                 key=lambda kv: (kv[1]["pts"], kv[1]["gd"], kv[1]["gf"]), reverse=True)


def qualification_status(group_teams: list[str], table: dict[str, dict],
                         total_group_games: int = 6) -> dict[str, str]:
    """
    Statut prudent par équipe. Hypothèse simplifiée : top 2 du groupe = qualifié.
    On ne tranche que si c'est MATHÉMATIQUEMENT certain.
    """
    status = {t: "alive" for t in group_teams}
    played_total = sum(v["played"] for v in table.values()) // 2  # matchs joués du groupe
    if played_total == 0:
        return status

    ranked = _rank(table)
    # points max atteignables par équipe = pts actuels + 3×(matchs restants de l'équipe)
    GAMES_PER_TEAM = 3
    for t in group_teams:
        cur = table.get(t, {"pts": 0, "played": 0})
        # nb de matchs restants pour CETTE équipe
        left_t = GAMES_PER_TEAM - cur.get("played", 0)
        cur["max"] = cur["pts"] + 3 * left_t

    # une équipe est QUALIFIÉE (top2) si au moins 2 équipes ne peuvent PAS la dépasser...
    # version prudente : on déclare qualifié seulement le leader avec une avance verrouillée.
    if len(ranked) >= 2 and played_total >= 4:   # après ~2 journées
        spts = ranked[1][1]["pts"]
        # combien d'équipes peuvent encore atteindre/dépasser la 2e place ?
        for t in group_teams:
            cur = table.get(t)
            if not cur:
                continue
            left_t = GAMES_PER_TEAM - cur["played"]
            # qualifié si même en perdant tout, personne (hors top) ne peut le sortir du top 2
            others_that_can_pass = sum(
                1 for o in group_teams if o != t and
                (table.get(o, {"pts": 0, "played": 0}).get("pts", 0)
                 + 3 * (GAMES_PER_TEAM - table.get(o, {"played": 0}).get("played", 0))) > cur["pts"]
            )
            if others_that_can_pass <= 1:
                status[t] = "qualified"
            # éliminé si son max < 3e meilleur potentiel garanti (prudent : max < pts du 2e)
            if cur["pts"] + 3 * left_t < spts and left_t < GAMES_PER_TEAM:
                status[t] = "eliminated"
    return status


def build_all_statuses(all_matches: list[dict]) -> dict[str, str]:
    """
    Calcule le statut de toutes les équipes (par groupe).
    all_matches : tous les matchs (avec 'stage' = 'Group X').
    Renvoie {team: status}.
    """
    groups: dict[str, list[dict]] = {}
    for m in all_matches:
        st = str(m.get("stage", ""))
        if st.startswith("Group"):
            groups.setdefault(st, []).append(m)

    out: dict[str, str] = {}
    for gname, gmatches in groups.items():
        teams = sorted({t for m in gmatches for t in (m["home"], m["away"])})
        table = compute_group_table(gmatches)
        out.update(qualification_status(teams, table))
    return out


def build_standings(all_matches: list[dict]) -> list[dict]:
    """
    Classement complet par groupe (pour l'affichage), avec TOUTES les équipes
    (même celles à 0 match), triées par pts > diff > buts marqués.
    Renvoie [{group, rows:[{rank, team, played, win, draw, loss, gf, ga, gd, pts}]}].
    100% dérivé des résultats RÉELS (matchs FINISHED).
    """
    groups: dict[str, list[dict]] = {}
    for m in all_matches:
        st = str(m.get("stage", ""))
        if st.startswith("Group"):
            groups.setdefault(st, []).append(m)

    out = []
    for gname in sorted(groups):
        gmatches = groups[gname]
        teams = sorted({t for m in gmatches for t in (m["home"], m["away"])})
        tab = {t: {"played": 0, "win": 0, "draw": 0, "loss": 0,
                   "gf": 0, "ga": 0, "gd": 0, "pts": 0} for t in teams}
        for m in gmatches:
            if m["status"] != "FINISHED" or m["home_goals"] is None:
                continue
            h, a = m["home"], m["away"]
            hg, ag = m["home_goals"], m["away_goals"]
            for t, gfor, gag in ((h, hg, ag), (a, ag, hg)):
                r = tab[t]
                r["played"] += 1; r["gf"] += gfor; r["ga"] += gag; r["gd"] += gfor - gag
                if gfor > gag: r["win"] += 1; r["pts"] += 3
                elif gfor == gag: r["draw"] += 1; r["pts"] += 1
                else: r["loss"] += 1
        ranked = sorted(tab.items(), key=lambda kv: (kv[1]["pts"], kv[1]["gd"], kv[1]["gf"]), reverse=True)
        rows = [{"rank": i + 1, "team": t, **r} for i, (t, r) in enumerate(ranked)]
        out.append({"group": gname, "rows": rows})
    return out

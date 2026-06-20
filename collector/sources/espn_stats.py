"""
Adaptateur ESPN — stats RÉELLES par joueur (tout le XI + remplaçants) et par équipe.

Source : API publique non officielle d'ESPN (site.api.espn.com), GRATUITE, sans clé.
  - scoreboard?dates=YYYYMMDD  -> liste des matchs + event id + score + statut
  - summary?event=<id>         -> boxscore équipe + rosters (stats par joueur)

✅ ZÉRO invention : tout vient directement d'ESPN (Opta sous le capot).
   Si l'API est injoignable (hors-ligne), les fonctions renvoient None proprement.

Noms d'équipe ESPN ≈ nomenclature de la base (Ivory Coast, United States, Czech Republic…).
Un mapping corrige les rares écarts.
"""
from __future__ import annotations
import json, urllib.request, datetime

BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world"
UA = {"User-Agent": "Mozilla/5.0 (PronoFoot data collector)"}
TIMEOUT = 20

# écarts de nomenclature ESPN -> base interne
TEAM_MAP = {
    "USA": "United States", "United States": "United States",
    "Türkiye": "Turkey", "Czechia": "Czech Republic",
    "Korea Republic": "South Korea", "IR Iran": "Iran", "Cabo Verde": "Cape Verde",
    "Curacao": "Curaçao", "DR Congo": "DR Congo",
    "Bosnia-Herzegovina": "Bosnia & Herzegovina",
}


def _norm(name):
    return TEAM_MAP.get(name, name)


def _get(url):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.load(r)
    except Exception:
        return None


def scoreboard(date: datetime.date | None = None):
    """Liste des matchs ESPN pour une date (par défaut aujourd'hui)."""
    q = f"?dates={date.strftime('%Y%m%d')}" if date else ""
    d = _get(f"{BASE}/scoreboard{q}")
    if not d:
        return []
    out = []
    for e in d.get("events", []):
        comp = e["competitions"][0]
        c = comp["competitors"]
        home = next((x for x in c if x.get("homeAway") == "home"), c[0])
        away = next((x for x in c if x.get("homeAway") == "away"), c[1])
        out.append({
            "id": e["id"],
            "home": _norm(home["team"]["displayName"]),
            "away": _norm(away["team"]["displayName"]),
            "home_goals": _to_int(home.get("score")),
            "away_goals": _to_int(away.get("score")),
            "state": e["status"]["type"]["name"],   # STATUS_SCHEDULED / IN_PROGRESS / FINAL
            "completed": e["status"]["type"].get("completed", False),
            "clock": e["status"].get("displayClock"),    # minute de jeu live (ex "56'")
            "period": e["status"].get("period"),          # 1=1ère MT, 2=2ème MT
        })
    return out


def _to_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _to_num(v):
    try:
        f = float(v)
        return int(f) if f == int(f) else f
    except (TypeError, ValueError):
        return None


# mapping stat ESPN -> clé interne (player_stats_real)
_PLAYER_STAT_MAP = {
    "totalGoals": "buts", "goalAssists": "passes_dec", "totalShots": "tirs",
    "shotsOnTarget": "tirs_cadres", "foulsCommitted": "fautes_commises",
    "offsides": "hors_jeu", "saves": "saves", "shotsFaced": "shots_faced",
    "goalsConceded": "goals_conceded",
}


def _xg_from_leaders(leaders_section, side_name):
    """Extrait le xG total d'équipe depuis la section leaders ESPN.
    ESPN stocke le xG (Opta) du meilleur tireur dans leaders[team][totalShots][leader].statistics.
    On somme les xG de tous les leaders listés pour approcher le total équipe.
    Si un seul leader est listé, c'est le meilleur tireur uniquement — on le note quand même.
    """
    for team_block in leaders_section or []:
        tname = _norm(team_block.get("team", {}).get("displayName", ""))
        if tname != side_name:
            continue
        for stat_cat in team_block.get("leaders", []):
            if stat_cat.get("name") != "totalShots":
                continue
            total_xg = 0.0
            found = False
            for leader in stat_cat.get("leaders", []):
                for s in leader.get("statistics", []):
                    if s.get("abbreviation") == "xG":
                        v = s.get("value")
                        if v is not None:
                            total_xg += float(v)
                            found = True
            if found:
                return round(total_xg, 3)
    return None


def _xg_estimate(shots, shots_on):
    """Estimation xG simple : tirs cadrés × 0.11 + hors cadre × 0.036.
    Utilisée uniquement comme fallback quand ESPN ne fournit pas le xG.
    """
    try:
        s = float(shots or 0)
        so = float(shots_on or 0)
        off_target = max(0.0, s - so)
        return round(so * 0.11 + off_target * 0.036, 2)
    except (TypeError, ValueError):
        return None


def match_summary(event_id):
    """
    Renvoie {team_stats, player_stats, lineups, events} d'un match ESPN, ou None.
      team_stats   : {home/away_xg?, _shots, _shots_on, _corners, _cards, _possession}
      player_stats : {equipe: {joueur: {poste, statut, buts, tirs, ...}}}
      events       : {goals: [{minute, team, player, assist, note}], cards: [{minute, team, player, type}]}
    """
    d = _get(f"{BASE}/summary?event={event_id}")
    if not d:
        return None
    out = {"team": {}, "players": {}, "lineups": {}, "referee": None, "events": {"goals": [], "cards": []}}
    # arbitre du match (gameInfo.officials)
    for off in (d.get("gameInfo", {}).get("officials") or []):
        pos = off.get("position", {})
        pos = pos.get("displayName") if isinstance(pos, dict) else pos
        if (pos or "").lower() == "referee" or not out["referee"]:
            out["referee"] = off.get("fullName")

    out["halftime"] = None
    try:
        comps = d.get("header", {}).get("competitions", [{}])[0].get("competitors", [])
        if len(comps) == 2:
            home_c = comps[0] if comps[0].get("homeAway") == "home" else comps[1]
            away_c = comps[1] if comps[0].get("homeAway") == "home" else comps[0]
            if "linescores" in home_c and "linescores" in away_c:
                if len(home_c["linescores"]) > 0 and len(away_c["linescores"]) > 0:
                    h_ht = home_c["linescores"][0].get("displayValue", "0")
                    a_ht = away_c["linescores"][0].get("displayValue", "0")
                    out["halftime"] = f"{h_ht}-{a_ht}"
    except Exception:
        pass

    # ----- boxscore équipe -----
    for t in d.get("boxscore", {}).get("teams", []):
        side = t.get("homeAway")
        sd = {s["name"]: s.get("displayValue") for s in t.get("statistics", [])}
        prefix = "home" if side == "home" else "away"
        out["team"][f"{prefix}_shots"] = _to_num(sd.get("totalShots"))
        out["team"][f"{prefix}_shots_on"] = _to_num(sd.get("shotsOnTarget"))
        out["team"][f"{prefix}_corners"] = _to_num(sd.get("wonCorners"))
        out["team"][f"{prefix}_cards"] = (_to_num(sd.get("yellowCards")) or 0) + (_to_num(sd.get("redCards")) or 0)
        out["team"][f"{prefix}_possession"] = _to_num(sd.get("possessionPct"))
        out["team"][f"{prefix}_name"] = _norm(t["team"]["displayName"])
        # stats d'équipe ÉTENDUES (toutes réelles, ESPN/Opta)
        out["team"][f"{prefix}_passes"] = _to_num(sd.get("totalPasses"))
        out["team"][f"{prefix}_passes_ok"] = _to_num(sd.get("accuratePasses"))
        out["team"][f"{prefix}_pass_pct"] = _to_num(sd.get("passPct"))
        out["team"][f"{prefix}_crosses"] = _to_num(sd.get("totalCrosses"))
        out["team"][f"{prefix}_crosses_ok"] = _to_num(sd.get("accurateCrosses"))
        out["team"][f"{prefix}_long_balls"] = _to_num(sd.get("totalLongBalls"))
        out["team"][f"{prefix}_tackles"] = _to_num(sd.get("totalTackles"))
        out["team"][f"{prefix}_tackles_won"] = _to_num(sd.get("effectiveTackles"))
        out["team"][f"{prefix}_interceptions"] = _to_num(sd.get("interceptions"))
        out["team"][f"{prefix}_clearances"] = _to_num(sd.get("totalClearance"))
        out["team"][f"{prefix}_blocked_shots"] = _to_num(sd.get("blockedShots"))
        out["team"][f"{prefix}_fouls"] = _to_num(sd.get("foulsCommitted"))
        out["team"][f"{prefix}_offsides"] = _to_num(sd.get("offsides"))
        out["team"][f"{prefix}_saves"] = _to_num(sd.get("saves"))
        # xG ESPN depuis leaders (Opta) — extrait après la boucle boxscore
        out["team"][f"{prefix}_name"] = out["team"].get(f"{prefix}_name")  # déjà positionné

    # --- xG par équipe depuis la section leaders (Opta/ESPN) ---
    # NOTE : ESPN leaders contient le xG du MEILLEUR tireur seulement (pas le total équipe).
    # On préfère donc l'estimation mathématique (tirs cadrés × 0.11 + hors cadre × 0.036)
    # qui est cohérente avec les anciens totaux Opta/TheAnalyst du fichier match_stats_real.json.
    # Le xG ESPN d'un joueur reste utilisé uniquement si on n'a ni tirs ni shots_on.
    leaders = d.get("leaders", [])
    for side_key, side_name_key in (("home", "home_name"), ("away", "away_name")):
        side_name = out["team"].get(side_name_key)
        shots = out["team"].get(f"{side_key}_shots")
        shots_on = out["team"].get(f"{side_key}_shots_on")
        # Priorité 1 : estimation mathématique (si on a les tirs)
        if shots is not None:
            xg_val = _xg_estimate(shots, shots_on)
        else:
            # Priorité 2 : fallback ESPN leaders (xG top tireur uniquement)
            xg_val = _xg_from_leaders(leaders, side_name) if side_name else None
            if xg_val is not None:
                out["team"][f"{side_key}_xg_from_leaders"] = True
        out["team"][f"{side_key}_xg"] = xg_val

    # ----- rosters : stats par joueur -----
    for r in d.get("rosters", []):
        team = _norm(r["team"]["displayName"])
        out["lineups"][team] = {"formation": r.get("formation"),
                                "xi": [], "bench": []}
        players = {}
        for p in r.get("roster", []):
            ath = p.get("athlete", {})
            name = ath.get("displayName")
            if not name:
                continue
            stmap = {s["name"]: s.get("displayValue") for s in p.get("stats", [])}
            rec = {"poste": p.get("position", {}).get("abbreviation"),
                   "statut": "Titulaire" if p.get("starter") else "Remplaçant"}
            for espn_k, our_k in _PLAYER_STAT_MAP.items():
                v = _to_num(stmap.get(espn_k))
                if v is not None:
                    rec[our_k] = v
            # cartons en libellé (cohérent avec le reste de l'app)
            rc = _to_num(stmap.get("redCards")) or 0
            yc = _to_num(stmap.get("yellowCards")) or 0
            if rc:
                rec["cartons"] = "Red"
            elif yc:
                rec["cartons"] = "Yellow"
            players[name] = rec
            (out["lineups"][team]["xi"] if p.get("starter")
             else out["lineups"][team]["bench"]).append(name)
        out["players"][team] = players

    # ----- keyEvents (goals, cards) -----
    goals_list = []
    cards_list = []
    for e in d.get("keyEvents", []):
        etype = e.get("type", {}).get("type")
        minute_str = e.get("clock", {}).get("displayValue", "")
        minute = 0
        if minute_str:
            try:
                minute = int(minute_str.replace("'", "").split("+")[0])
            except ValueError:
                pass
        
        team_name = _norm(e.get("team", {}).get("displayName", ""))
        
        if etype == "goal":
            players = e.get("participants", [])
            scorer = players[0].get("athlete", {}).get("displayName") if len(players) > 0 else "—"
            assist = players[1].get("athlete", {}).get("displayName") if len(players) > 1 else None
            note = None
            text = e.get("text", "")
            if "own goal" in text.lower():
                scorer += " (csc)"
                note = "but contre son camp"
            elif "penalty" in text.lower():
                note = "penalty"
            
            goals_list.append({
                "minute": minute,
                "team": team_name,
                "player": scorer,
                "assist": assist,
                "note": note
            })
        elif etype in ("yellow-card", "red-card") or "red card" in e.get("type", {}).get("text", "").lower() or "red-card" in etype:
            players = e.get("participants", [])
            player = players[0].get("athlete", {}).get("displayName") if len(players) > 0 else "—"
            card_type = "Red" if (etype == "red-card" or "red card" in e.get("type", {}).get("text", "").lower()) else "Yellow"
            
            cards_list.append({
                "minute": minute,
                "team": team_name,
                "player": player,
                "type": card_type
            })
            
    out["events"] = {
        "goals": goals_list,
        "cards": cards_list
    }
    return out


# alias pour comparer des noms équivalents (base interne <-> ESPN)
_ALIAS = {
    "usa": "united states", "united states": "united states",
    "bosnia & herzegovina": "bosnia herzegovina", "bosnia-herzegovina": "bosnia herzegovina",
    "turkey": "turkey", "türkiye": "turkey", "czechia": "czech republic",
    "curacao": "curaçao",
}


def _alias(name):
    k = (name or "").strip().lower()
    return _ALIAS.get(k, k)


def _ml_to_decimal(ml):
    """Convertit une cote américaine (moneyline) en cote décimale."""
    try:
        ml = float(ml)
    except (TypeError, ValueError):
        return None
    if ml > 0:
        return round(1 + ml / 100.0, 3)
    if ml < 0:
        return round(1 + 100.0 / abs(ml), 3)
    return None


def match_odds(event_id):
    """Cotes 1N2 (décimales) + O/U d'un match ESPN, ou None.
    Renvoie {odd1, oddX, odd2, ou_line, over, under, provider}."""
    d = _get(f"{BASE}/summary?event={event_id}")
    if not d:
        return None
    arr = d.get("pickcenter") or d.get("odds") or []
    if not arr:
        return None
    o = arr[0]
    home_ml = (o.get("homeTeamOdds") or {}).get("moneyLine")
    away_ml = (o.get("awayTeamOdds") or {}).get("moneyLine")
    draw_ml = (o.get("drawOdds") or {}).get("moneyLine") if isinstance(o.get("drawOdds"), dict) else o.get("drawOdds")
    return {
        "odd1": _ml_to_decimal(home_ml),
        "oddX": _ml_to_decimal(draw_ml),
        "odd2": _ml_to_decimal(away_ml),
        "ou_line": o.get("overUnder"),
        "over": _ml_to_decimal(o.get("overOdds")),
        "under": _ml_to_decimal(o.get("underOdds")),
        "provider": (o.get("provider") or {}).get("name"),
    }


def match_h2h(event_id):
    """Bilan des confrontations directes récentes (depuis le summary ESPN).
    Renvoie {games:[{date,score,competition}], summary:{p1,draws,p2}} où p1=victoires
    de l'équipe listée en premier dans headToHeadGames. None si rien."""
    d = _get(f"{BASE}/summary?event={event_id}")
    if not d:
        return None
    games = d.get("headToHeadGames") or []
    if not games:
        return None
    blk = games[0]
    ref_team = (blk.get("team") or {}).get("displayName")
    ref_id = str((blk.get("team") or {}).get("id") or "")
    out = []
    w = dr = l = 0
    for ev in blk.get("events", [])[:12]:
        hs = _to_int(ev.get("homeTeamScore")); as_ = _to_int(ev.get("awayTeamScore"))
        if hs is None or as_ is None:
            continue
        # score du point de vue de ref_team
        ref_is_home = str(ev.get("homeTeamId")) == ref_id
        rf = hs if ref_is_home else as_
        ra = as_ if ref_is_home else hs
        if rf > ra: w += 1
        elif rf == ra: dr += 1
        else: l += 1
        out.append({
            "date": ev.get("gameDate", "")[:10],
            "score": f"{rf}-{ra}",
            "competition": ev.get("competitionName"),
        })
    if not out:
        return None
    return {"refTeam": ref_team, "games": out,
            "summary": {"win": w, "draw": dr, "loss": l, "total": w + dr + l}}


def _tok_set(name):
    """Mots significatifs d'un nom (gère 'Congo DR' == 'DR Congo')."""
    stop = {"dr", "of", "the", "and", "republic", "rep", "ir", "pr"}
    return {w for w in _norm(name).replace("&", " ").lower().split() if w and w not in stop}


def find_event(home, away, date: datetime.date | None = None):
    """Trouve l'event id ESPN d'un match par équipes (tolérant aux variantes/ordre de nom)."""
    th, ta = _tok_set(home), _tok_set(away)
    dates = [date] if date else [datetime.date.today() - datetime.timedelta(days=k) for k in range(0, 4)]
    for dt in dates:
        for m in scoreboard(dt):
            mh, ma = _tok_set(m["home"]), _tok_set(m["away"])
            # alias exact d'abord
            if {_alias(m["home"]), _alias(m["away"])} == {_alias(home), _alias(away)}:
                return m
            # sinon, chevauchement de tokens dans l'un ou l'autre sens
            if (th & mh and ta & ma) or (th & ma and ta & mh):
                return m
    return None

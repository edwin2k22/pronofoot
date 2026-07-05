"""
Build player/team action profiles from ESPN commentary.

The commentary is event text, not a betting market. This module converts it into
reproducible counters: shots, shots on target, shot assists, fouls, corners, etc.
No missing action is invented.
"""
from __future__ import annotations

import json
import os
import re
import unicodedata

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
EVENTS_PATH = os.path.join(DATA_DIR, "match_events_real.json")

_CACHE = None


TEAM_ALIASES = {
    "cote d ivoire": "ivory coast",
    "cote divoire": "ivory coast",
    "usa": "united states",
    "united states": "united states",
    "bosnia and herzegovina": "bosnia herzegovina",
    "bosnia herzegovina": "bosnia herzegovina",
}


def _clean(value):
    return re.sub(r"\s+", " ", str(value or "").strip(" .")).strip()


def _key(value):
    text = unicodedata.normalize("NFD", _clean(value))
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _team_key(value):
    key = _key(value)
    return TEAM_ALIASES.get(key, key)


def _name_key(value):
    return _key(str(value or "").split("(")[0])


def _last_key(value):
    parts = _name_key(value).split()
    return parts[-1] if parts else ""


def _resolve_team(raw_team, home, away):
    raw_key = _team_key(raw_team)
    if raw_key == _team_key(home):
        return home
    if raw_key == _team_key(away):
        return away
    return _clean(raw_team)


def _opponent(team, home, away):
    if _team_key(team) == _team_key(home):
        return away
    if _team_key(team) == _team_key(away):
        return home
    return None


def _inc(bucket, field, amount=1):
    bucket[field] = bucket.get(field, 0) + amount


def _team(profiles, team):
    tk = _team_key(team)
    teams = profiles.setdefault("teams", {})
    rec = teams.setdefault(tk, {
        "name": _clean(team),
        "matches": 0,
        "shotsFor": 0,
        "shotsOnFor": 0,
        "shotsBlockedFor": 0,
        "shotsAllowed": 0,
        "shotsOnAllowed": 0,
        "cornersFor": 0,
        "cornersAllowed": 0,
        "foulsCommitted": 0,
        "foulsDrawn": 0,
        "offsides": 0,
        "cards": 0,
    })
    if not rec.get("name"):
        rec["name"] = _clean(team)
    return rec


def _player(profiles, team, name):
    if not name:
        return None
    tk = _team_key(team)
    pk = _name_key(name)
    if not pk:
        return None
    by_team = profiles.setdefault("players", {}).setdefault(tk, {})
    rec = by_team.setdefault(pk, {
        "name": _clean(name),
        "team": _clean(team),
        "shots": 0,
        "shotsOn": 0,
        "shotsBlocked": 0,
        "shotsOff": 0,
        "goals": 0,
        "woodwork": 0,
        "createdShots": 0,
        "foulsCommitted": 0,
        "foulsDrawn": 0,
        "offsides": 0,
        "cards": 0,
        "saves": 0,
    })
    return rec


def _extract_player_team(segment):
    m = re.match(r"(?P<player>.+?)\s+\((?P<team>[^)]+)\)", segment or "")
    if not m:
        return None
    return _clean(m.group("player")), _clean(m.group("team"))


def _assist_name(text):
    m = re.search(r"\bAssisted by\s+(.+?)(?:\s+with\b|\s+following\b|\.|$)", text or "")
    return _clean(m.group(1)) if m else None


def _shot_actor(comment):
    text = comment.get("text") or ""
    typ = (comment.get("type") or "").lower()
    if text.startswith("Own Goal"):
        return None
    detail = None
    if text.startswith("Goal!"):
        parts = text.split(". ", 1)
        detail = parts[1] if len(parts) > 1 else ""
    elif text.startswith(("Attempt missed.", "Attempt saved.", "Attempt blocked.")):
        detail = text.split(". ", 1)[1] if ". " in text else ""
    elif text.startswith("Penalty missed."):
        detail = text.split(". ", 1)[1] if ". " in text else ""
    elif "hit woodwork" in typ or "hits the bar" in text or "hits the post" in text:
        detail = text
    else:
        return None
    actor = _extract_player_team(detail)
    if not actor:
        return None
    kind = "off"
    if "blocked" in typ or text.startswith("Attempt blocked."):
        kind = "blocked"
    elif "target" in typ or text.startswith("Attempt saved."):
        kind = "on"
    elif "goal" in typ or text.startswith("Goal!"):
        kind = "goal"
    elif "woodwork" in typ or "hits the bar" in text or "hits the post" in text:
        kind = "woodwork"
    elif text.startswith("Penalty missed."):
        kind = "off"
    return {"player": actor[0], "team": actor[1], "kind": kind, "assist": _assist_name(text)}


def _keeper_save(text):
    m = re.search(r"\bsaved\b.*?\bby\s+(.+?)\s+\(([^)]+)\)", text or "")
    if not m:
        return None
    return _clean(m.group(1)), _clean(m.group(2))


def _corner_team(text):
    m = re.match(r"Corner,\s*([^.]+)\.", text or "")
    return _clean(m.group(1)) if m else None


def _foul_by(text):
    m = re.match(r"Foul by\s+(.+?)\s+\(([^)]+)\)", text or "")
    return (_clean(m.group(1)), _clean(m.group(2))) if m else None


def _foul_won(text):
    m = re.match(r"(.+?)\s+\(([^)]+)\)\s+wins a free kick", text or "")
    return (_clean(m.group(1)), _clean(m.group(2))) if m else None


def _offside(text):
    m = re.match(r"Offside,\s*([^.]+)\.\s*(.+?)\s+is caught offside", text or "")
    if not m:
        return None
    return _clean(m.group(2)), _clean(m.group(1))


def _card(text):
    m = re.match(r"(.+?)\s+\(([^)]+)\)\s+is shown the (yellow|red)", text or "", re.I)
    return (_clean(m.group(1)), _clean(m.group(2))) if m else None


def build_profiles(events_data=None):
    if events_data is None:
        try:
            with open(EVENTS_PATH, encoding="utf-8") as f:
                events_data = json.load(f)
        except (OSError, ValueError):
            events_data = {}

    profiles = {"teams": {}, "players": {}}
    for match_key, payload in (events_data or {}).items():
        if not isinstance(payload, dict) or "|" not in match_key:
            continue
        home, away = match_key.split("|", 1)
        seen_teams = {_team_key(home), _team_key(away)}
        for team in (home, away):
            _inc(_team(profiles, team), "matches")

        for comment in payload.get("commentary") or []:
            text = comment.get("text") or ""
            typ = comment.get("type") or ""

            shot = _shot_actor(comment)
            if shot:
                team = _resolve_team(shot["team"], home, away)
                opp = _opponent(team, home, away)
                if _team_key(team) in seen_teams:
                    t = _team(profiles, team)
                    p = _player(profiles, team, shot["player"])
                    _inc(t, "shotsFor")
                    if p:
                        _inc(p, "shots")
                    if shot["kind"] in ("on", "goal"):
                        _inc(t, "shotsOnFor")
                        if p:
                            _inc(p, "shotsOn")
                    elif shot["kind"] == "blocked":
                        _inc(t, "shotsBlockedFor")
                        if p:
                            _inc(p, "shotsBlocked")
                    elif shot["kind"] == "woodwork":
                        if p:
                            _inc(p, "woodwork")
                    else:
                        if p:
                            _inc(p, "shotsOff")
                    if shot["kind"] == "goal" and p:
                        _inc(p, "goals")
                    if shot.get("assist"):
                        ap = _player(profiles, team, shot["assist"])
                        if ap:
                            _inc(ap, "createdShots")
                    if opp:
                        ot = _team(profiles, opp)
                        _inc(ot, "shotsAllowed")
                        if shot["kind"] in ("on", "goal"):
                            _inc(ot, "shotsOnAllowed")

                save = _keeper_save(text)
                if save:
                    k_team = _resolve_team(save[1], home, away)
                    kp = _player(profiles, k_team, save[0])
                    if kp:
                        _inc(kp, "saves")
                continue

            corner = _corner_team(text)
            if corner:
                team = _resolve_team(corner, home, away)
                opp = _opponent(team, home, away)
                if _team_key(team) in seen_teams:
                    _inc(_team(profiles, team), "cornersFor")
                    if opp:
                        _inc(_team(profiles, opp), "cornersAllowed")
                continue

            fb = _foul_by(text)
            if fb:
                team = _resolve_team(fb[1], home, away)
                if _team_key(team) in seen_teams:
                    _inc(_team(profiles, team), "foulsCommitted")
                    p = _player(profiles, team, fb[0])
                    if p:
                        _inc(p, "foulsCommitted")
                continue

            fw = _foul_won(text)
            if fw:
                team = _resolve_team(fw[1], home, away)
                if _team_key(team) in seen_teams:
                    _inc(_team(profiles, team), "foulsDrawn")
                    p = _player(profiles, team, fw[0])
                    if p:
                        _inc(p, "foulsDrawn")
                continue

            off = _offside(text)
            if off:
                team = _resolve_team(off[1], home, away)
                if _team_key(team) in seen_teams:
                    _inc(_team(profiles, team), "offsides")
                    p = _player(profiles, team, off[0])
                    if p:
                        _inc(p, "offsides")
                continue

            if "card" in typ.lower():
                cd = _card(text)
                if cd:
                    team = _resolve_team(cd[1], home, away)
                    if _team_key(team) in seen_teams:
                        _inc(_team(profiles, team), "cards")
                        p = _player(profiles, team, cd[0])
                        if p:
                            _inc(p, "cards")

    return profiles


def load_profiles():
    global _CACHE
    if _CACHE is None:
        _CACHE = build_profiles()
    return _CACHE


def reset_cache():
    global _CACHE
    _CACHE = None


def _per(team_profile, field):
    n = team_profile.get("matches") or 0
    return (team_profile.get(field, 0) / n) if n else None


def _global_per(profiles, field):
    total = games = 0
    for team in (profiles.get("teams") or {}).values():
        n = team.get("matches") or 0
        total += team.get(field, 0)
        games += n
    return (total / games) if games else None


def _factor(attack_rate, allowed_rate, global_rate, sample):
    if not global_rate or global_rate <= 0:
        return 1.0
    atk = global_rate if attack_rate is None else attack_rate
    allowed = global_rate if allowed_rate is None else allowed_rate
    raw = ((atk / global_rate) + (allowed / global_rate)) / 2
    raw = max(0.55, min(1.50, raw))
    shrink = max(0.0, min(1.0, sample / 5.0))
    return round(1 + (raw - 1) * shrink, 3)


def matchup_profile(team, opponent, profiles=None):
    profiles = profiles or load_profiles()
    teams = profiles.get("teams") or {}
    tk, ok = _team_key(team), _team_key(opponent)
    tp = teams.get(tk, {"name": team, "matches": 0})
    op = teams.get(ok, {"name": opponent, "matches": 0})
    sample = min(tp.get("matches", 0) or 0, op.get("matches", 0) or 0)

    factors = {
        "shots": _factor(_per(tp, "shotsFor"), _per(op, "shotsAllowed"), _global_per(profiles, "shotsFor"), sample),
        "shotsOn": _factor(_per(tp, "shotsOnFor"), _per(op, "shotsOnAllowed"), _global_per(profiles, "shotsOnFor"), sample),
        "corners": _factor(_per(tp, "cornersFor"), _per(op, "cornersAllowed"), _global_per(profiles, "cornersFor"), sample),
        "fouls": _factor(_per(tp, "foulsCommitted"), _per(op, "foulsDrawn"), _global_per(profiles, "foulsCommitted"), sample),
    }
    players = profiles.get("players", {}).get(tk, {})
    last_players = {}
    for rec in players.values():
        lk = _last_key(rec.get("name"))
        if lk and lk not in last_players:
            last_players[lk] = rec

    def rounded_profile(src):
        return {
            "matches": src.get("matches", 0) or 0,
            "shotsFor": round(_per(src, "shotsFor") or 0, 2),
            "shotsAllowed": round(_per(src, "shotsAllowed") or 0, 2),
            "shotsOnFor": round(_per(src, "shotsOnFor") or 0, 2),
            "shotsOnAllowed": round(_per(src, "shotsOnAllowed") or 0, 2),
            "cornersFor": round(_per(src, "cornersFor") or 0, 2),
            "cornersAllowed": round(_per(src, "cornersAllowed") or 0, 2),
            "foulsCommitted": round(_per(src, "foulsCommitted") or 0, 2),
            "foulsDrawn": round(_per(src, "foulsDrawn") or 0, 2),
        }

    return {
        "team": rounded_profile(tp),
        "opponent": rounded_profile(op),
        "factors": factors,
        "sample": sample,
        "players": players,
        "lastPlayers": last_players,
    }


def player_event_stats(profile, name):
    if not profile:
        return {}
    return ((profile.get("players") or {}).get(_name_key(name))
            or (profile.get("lastPlayers") or {}).get(_last_key(name))
            or {})

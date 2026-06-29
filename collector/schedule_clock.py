"""
Horloge du calendrier — calcule les coups d'envoi en UTC.

openfootball donne des heures avec fuseau intégré, ex : "13:00 UTC-6".
On les convertit en datetime UTC pour que le scheduler sache exactement
quand chaque match commence (et donc quand activer le mode live).
"""
from __future__ import annotations
import re, datetime
from .sources import openfootball_wc

_TZ_RE = re.compile(r"(\d{1,2}):(\d{2})\s*UTC([+-]\d{1,2})")
MATCH_DURATION_MIN = 200   # marge large (prolongations possibles + tirs au but)


def kickoff_utc(date_str: str, time_str: str) -> datetime.datetime | None:
    """'2026-06-11' + '13:00 UTC-6' -> datetime UTC (aware)."""
    if not date_str or not time_str:
        return None
    m = _TZ_RE.search(time_str)
    if not m:
        return None
    hh, mm, off = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        y, mo, d = map(int, date_str.split("-"))
    except ValueError:
        return None
    # heure locale du stade -> UTC : UTC = local - offset
    local = datetime.datetime(y, mo, d, hh, mm, tzinfo=datetime.timezone(datetime.timedelta(hours=off)))
    return local.astimezone(datetime.timezone.utc)


def all_kickoffs() -> list[dict]:
    """Liste triée des matchs avec leur coup d'envoi UTC + état théorique."""
    sched = openfootball_wc.load_schedule()
    out = []
    for mt in sched.get("matches", []):
        t1, t2 = mt.get("team1"), mt.get("team2")
        if not t1 or not t2 or any(c in t1 for c in "0123456789/"):
            continue
        ko = kickoff_utc(mt.get("date", ""), mt.get("time", ""))
        if not ko:
            continue
        out.append({"home": t1, "away": t2, "kickoff": ko,
                    "played": bool(mt.get("score", {}).get("ft"))})
    out.sort(key=lambda x: x["kickoff"])
    return out


def now_utc() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def live_window(pre_min: int = 10, prematch_min: int = 30):
    """
    Analyse l'instant présent et renvoie un état pour le scheduler :
      - 'LIVE'     : au moins un match est en cours (fenêtre coup d'envoi → +120 min)
      - 'PREMATCH' : un match commence dans < prematch_min (ex 30 min) -> on va chercher
                     compos officielles + cotes à jour et on recalcule l'issue
      - 'SOON'     : un match commence dans < pre_min minutes (veille rapprochée)
      - 'IDLE'     : rien avant longtemps -> on peut dormir
    + le datetime du prochain coup d'envoi et les matchs concernés.
    """
    now = now_utc()
    kos = all_kickoffs()
    live, upcoming = [], []
    for m in kos:
        start = m["kickoff"]
        end = start + datetime.timedelta(minutes=MATCH_DURATION_MIN)
        if start <= now <= end:
            live.append(m)
        elif start > now:
            upcoming.append(m)

    next_ko = upcoming[0]["kickoff"] if upcoming else None
    delta = (next_ko - now) if next_ko else None
    if live:
        state = "LIVE"
    elif delta is not None and delta <= datetime.timedelta(minutes=pre_min):
        state = "SOON"
    elif delta is not None and delta <= datetime.timedelta(minutes=prematch_min):
        state = "PREMATCH"
    else:
        state = "IDLE"

    # matchs entrant dans la fenêtre pré-match (≤ prematch_min)
    prematch = [m for m in upcoming
                if (m["kickoff"] - now) <= datetime.timedelta(minutes=prematch_min)]

    return {
        "state": state,
        "now": now,
        "next_kickoff": next_ko,
        "live_matches": live,
        "prematch_matches": prematch,
        "next_match": upcoming[0] if upcoming else None,
        "seconds_to_next": (next_ko - now).total_seconds() if next_ko else None,
    }


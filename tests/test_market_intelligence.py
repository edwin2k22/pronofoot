from collector.db import database as db
from collector.pipeline import _build_market_intelligence


def _finish(conn, home, away, hg, ag, hc=3, ac=3, hcard=1, acard=1, day=1):
    conn.execute(
        """
        INSERT INTO matches(
            competition, stage, utc_date, home, away, status,
            home_goals, away_goals, home_corners, away_corners, home_cards, away_cards
        ) VALUES ('CDM 2026', 'Group A', ?, ?, ?, 'FINISHED', ?, ?, ?, ?, ?, ?)
        """,
        (f"2026-06-{day:02d} 12:00 UTC", home, away, hg, ag, hc, ac, hcard, acard),
    )


def test_market_intelligence_blocks_over_when_team_history_is_under():
    conn = db.init_db(":memory:")
    for day in range(1, 5):
        _finish(conn, "LowA", f"Rival{day}", 1, 0, day=day)
        _finish(conn, "LowB", f"Other{day}", 0, 0, day=day)

    intel = _build_market_intelligence(
        conn,
        {"home": "LowA", "away": "LowB"},
        {"p1": 0.44, "pX": 0.31, "p2": 0.25},
        {"over": 0.72, "btts": 0.38},
        {"line": 7.5, "over": 0.42, "under": 0.58},
        {"line": 3.5, "over": 0.45, "under": 0.55},
        0.80,
    )

    ou = next(c for c in intel["checks"] if c["market"] == "OU")
    assert ou["verdict"] == "avoid"
    assert "OU" in intel["noBetMarkets"]
    assert intel["adjustedConfidence"] < 0.80


def test_market_intelligence_supports_over_when_both_profiles_are_open():
    conn = db.init_db(":memory:")
    for day in range(1, 5):
        _finish(conn, "OpenA", f"Rival{day}", 3, 1, hc=6, ac=5, day=day)
        _finish(conn, "OpenB", f"Other{day}", 2, 2, hc=5, ac=6, day=day)

    intel = _build_market_intelligence(
        conn,
        {"home": "OpenA", "away": "OpenB"},
        {"p1": 0.52, "pX": 0.25, "p2": 0.23},
        {"over": 0.74, "btts": 0.66},
        {"line": 7.5, "over": 0.61, "under": 0.39},
        {"line": 3.5, "over": 0.45, "under": 0.55},
        0.70,
    )

    ou = next(c for c in intel["checks"] if c["market"] == "OU")
    assert ou["verdict"] == "support"
    assert intel["adjustedConfidence"] > 0.70

from collector.pipeline import _refresh_preserved_match_identity


def test_preserved_prediction_identity_uses_current_fixture_names():
    old = {
        "id": 92,
        "league": "CDM 2026 · Round of 16",
        "date": "2026-07-05 18:00 UTC-6",
        "home": "Mexico",
        "away": "W80",
        "prediction": {"p1": 0.88, "pX": 0.08, "p2": 0.04},
    }
    current = {
        "home": "Mexico",
        "away": "England",
        "utc_date": "2026-07-05 18:00 UTC-6",
        "stage": "Round of 16",
    }

    _refresh_preserved_match_identity(old, current)

    assert old["home"] == "Mexico"
    assert old["away"] == "England"
    assert old["league"] == "CDM 2026 · Round of 16"

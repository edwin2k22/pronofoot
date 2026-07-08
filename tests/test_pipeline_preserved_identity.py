from collector import pipeline


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

    pipeline._refresh_preserved_match_identity(old, current)

    assert old["home"] == "Mexico"
    assert old["away"] == "England"
    assert old["league"] == "CDM 2026 · Round of 16"


def test_preserved_prediction_hydrates_missing_referee_from_espn(monkeypatch):
    old = {
        "id": 92,
        "home": "Mexico",
        "away": "England",
        "sources": ["free-mode"],
        "prediction": {"p1": 0.88, "cards": {}},
    }
    current = {
        "home": "Mexico",
        "away": "England",
        "utc_date": "2026-07-05 18:00 UTC-6",
        "stage": "Round of 16",
    }

    monkeypatch.setattr(pipeline, "_real_referee",
                        lambda home, away: "Alireza Faghani")
    monkeypatch.setattr(
        pipeline.refform,
        "severity",
        lambda name: {"avg": 4.2, "n": 2, "source": "ESPN réel + prior"},
    )

    pipeline._refresh_preserved_match_identity(old, current)

    referee = old["prediction"]["referee"]
    assert referee["name"] == "Alireza Faghani"
    assert referee["source"] == "ESPN (réel)"
    assert referee["severity"] == 4.2
    assert old["prediction"]["cards"]["refSeverity"]["avg"] == 4.2
    assert "ESPN (arbitre réel)" in old["sources"]

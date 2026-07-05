from collector.models import best_picks


def test_watch_guard_blocks_risky_1n2_but_keeps_dnb_safety_net():
    match = {
        "status": "SCHEDULED",
        "home": "Alpha",
        "away": "Beta",
        "prediction": {
            "p1": 0.88,
            "pX": 0.09,
            "p2": 0.03,
            "drawNoBet": {"home": 0.96, "away": 0.04},
            "marketIntelligence": {
                "checks": [{"market": "1N2", "verdict": "watch", "impact": -1}]
            },
        },
    }

    picks = best_picks.select_for_match(match)

    assert not any(pick["market"] == "1N2" for pick in picks)
    assert any(pick["market"] == "DNB" for pick in picks)


def test_measure_reliability_uses_market_guards():
    match = {
        "status": "FINISHED",
        "home": "Alpha",
        "away": "Beta",
        "analysis": {"realScore": "0-1"},
        "prediction": {
            "p1": 0.88,
            "pX": 0.09,
            "p2": 0.03,
            "marketIntelligence": {
                "checks": [{"market": "1N2", "verdict": "watch", "impact": -1}]
            },
        },
    }

    reliability = best_picks.measure_reliability([match])

    assert reliability["byTier"]["strong"]["total"] == 0


def test_btts_value_requires_a_clearer_probability_edge():
    assert best_picks.tier_of(0.69, best_picks.TIERS, "BTTS") is None
    assert best_picks.tier_of(0.72, best_picks.TIERS, "BTTS") == "value"

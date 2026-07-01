from __future__ import annotations

from collector.models import pnl


def _match(p1, odd1):
    return {
        "status": "FINISHED",
        "odd1": odd1,
        "oddX": 3.0,
        "odd2": 3.0,
        "analysis": {"realScore": "1-0"},
        "prediction": {"p1": p1, "pX": 0.15, "p2": 0.10},
    }


def test_value_pnl_ignores_small_positive_edges():
    result = pnl.value_pnl([_match(0.60, 2.0)])

    assert result["bets"] == 0


def test_value_pnl_keeps_market_floor_edges():
    result = pnl.value_pnl([_match(0.75, 2.0)])

    assert result["bets"] == 1
    assert result["wins"] == 1
    assert result["pnl"] == 1.0

from __future__ import annotations

import pytest

from collector.models import ensemble as ens


def test_draw_bias_preserves_partition_and_raises_draw():
    p1, px, p2 = ens.apply_draw_bias(0.50, 0.20, 0.30, 0.06)

    assert p1 + px + p2 == pytest.approx(1.0, abs=1e-9)
    assert px > 0.20


def test_temperature_learning_detects_draw_underestimate():
    samples = (
        [{"p1": 0.60, "pX": 0.15, "p2": 0.25, "outcome": "X"}] * 12
        + [{"p1": 0.60, "pX": 0.15, "p2": 0.25, "outcome": "1"}] * 8
    )

    _, meta = ens.learn_temperature(samples)

    assert meta["drawBias"] > 0
    assert meta["drawBiasRaw"] > 0


def test_market_probs_removes_overround():
    p1, px, p2 = ens.market_probs(2.0, 3.5, 4.0)

    assert p1 + px + p2 == pytest.approx(1.0, abs=1e-9)
    assert p1 > px > p2


def test_combine_accepts_market_model_and_caps_weight():
    combined = ens.combine(
        (0.45, 0.30, 0.25),
        (0.44, 0.28, 0.28),
        (0.40, 0.30, 0.30),
        market_p=(0.70, 0.20, 0.10),
        weights={"elo": 0.1, "grid": 0.1, "form": 0.1, "market": 0.7},
    )

    assert combined["p1"] + combined["pX"] + combined["p2"] == pytest.approx(1.0, abs=2e-4)
    assert combined["weights"]["market"] <= ens.MAX_MARKET_WEIGHT + 1e-9
    assert combined["p1"] < 0.70


def test_combine_still_supports_legacy_three_model_weights():
    combined = ens.combine(
        (0.50, 0.25, 0.25),
        (0.45, 0.30, 0.25),
        (0.40, 0.30, 0.30),
        weights={"elo": 0.4, "grid": 0.4, "form": 0.2},
    )

    assert combined["p1"] + combined["pX"] + combined["p2"] == pytest.approx(1.0, abs=2e-4)
    assert "market" not in combined["weights"]

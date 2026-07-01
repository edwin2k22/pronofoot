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

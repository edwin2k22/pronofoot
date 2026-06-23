"""Tests du calibrage Dixon-Coles / effet de choc (calibrate.py) et du shrinkage.

Propriétés invariantes :
- calibrate renvoie toujours rho et gamma dans les bornes raisonnables
- calibrate sans match -> prior (ne plante pas)
- shrinkage Bayésien ramène vers le prior quand n est petit, vers l'observé quand n grand
- bias_adjust et scale_factor sont bornés et neutres sans données
"""
from __future__ import annotations

import pytest

from collector.models import calibrate as cal
from collector.models import shrinkage as shr


# ---------- calibrate ----------
class TestCalibrate:
    def test_no_samples_returns_prior(self):
        r = cal.calibrate([])
        assert r["rho"] == cal.PRIOR_RHO
        assert r["gamma"] == cal.PRIOR_GAMMA
        assert r["n_matches"] == 0

    def test_rho_in_reasonable_range(self):
        # 20 matchs réalistes (lambda ~1.3, scores ~0-3)
        samples = [(1.3, 1.3, 1, 1), (1.5, 1.0, 2, 0), (1.0, 1.5, 0, 2),
                   (1.4, 1.4, 1, 0), (1.2, 1.2, 0, 0)] * 4
        r = cal.calibrate(samples)
        assert -0.15 <= r["rho"] <= 0.05
        assert 0.0 <= r["gamma"] <= 0.15

    def test_shrinkage_pulls_toward_prior_with_few_matches(self):
        """Avec peu de matchs, le résultat reste proche du prior."""
        samples = [(1.3, 1.3, 0, 0)]  # un seul match serré
        r = cal.calibrate(samples)
        # rho tiré vers le prior DEFAULT_RHO (-0.06), pas à l'extrême -0.12
        assert abs(r["rho"] - cal.PRIOR_RHO) < 0.05

    def test_log_likelihood_nonnull_with_samples(self):
        samples = [(1.3, 1.3, 1, 1), (1.5, 1.0, 2, 0)]
        r = cal.calibrate(samples)
        assert r["log_likelihood"] is not None
        assert isinstance(r["log_likelihood"], float)


# ---------- bias_adjust ----------
class TestBiasAdjust:
    def test_no_data_is_neutral(self):
        r = cal.bias_adjust([], [])
        assert r["shift"] == 0.0
        assert r["n"] == 0

    def test_shift_bounded(self):
        preds = [0.1] * 20
        obs = [1] * 20  # énorme sous-estimation
        r = cal.bias_adjust(preds, obs)
        assert -0.15 <= r["shift"] <= 0.15

    def test_neutral_when_no_systematic_bias(self):
        preds = [0.5, 0.5, 0.5, 0.5]
        obs = [0, 1, 0, 1]  # moyenne 0.5 = prédiction -> pas de biais
        r = cal.bias_adjust(preds, obs)
        assert abs(r["shift"]) < 0.05


# ---------- scale_factor ----------
class TestScaleFactor:
    def test_no_data_returns_prior(self):
        r = cal.scale_factor([], [], prior_factor=1.0)
        assert r["factor"] == 1.0
        assert r["n"] == 0

    def test_factor_bounded(self):
        preds = [10.0] * 5
        obs = [100.0] * 5  # sous-estimation massive
        r = cal.scale_factor(preds, obs, prior_factor=1.0)
        assert 0.5 <= r["factor"] <= 1.6

    def test_accurate_prediction_stays_near_one(self):
        preds = [5.0, 5.0, 5.0]
        obs = [5.0, 5.0, 5.0]
        r = cal.scale_factor(preds, obs, prior_factor=1.0)
        assert r["factor"] == pytest.approx(1.0, abs=0.05)


# ---------- shrinkage ----------
class TestShrinkage:
    def test_no_obs_returns_prior(self):
        assert shr.shrink(99.9, n=0, prior=5.0) == 5.0

    def test_few_obs_close_to_prior(self):
        """Avec peu de données, on reste près du prior."""
        val = shr.shrink(observed_mean=10.0, n=1, prior=5.0, k=4.0)
        # (1*10 + 4*5) / 5 = 6.0 -> entre observé et prior, plus près du prior
        assert 5.0 < val < 10.0
        assert val < 7.5

    def test_many_obs_close_to_observed(self):
        """Avec beaucoup de données, on converge vers l'observé."""
        val = shr.shrink(observed_mean=10.0, n=1000, prior=5.0, k=4.0)
        assert val == pytest.approx(10.0, abs=0.1)

    def test_update_running_mean_is_consistent(self):
        """La moyenne incrémentale doit converger vers la vraie moyenne."""
        vals = [1.0, 2.0, 3.0, 4.0, 5.0]
        mean, n = 0.0, 0
        for v in vals:
            mean, n = shr.update_running_mean(mean, n, v)
        assert n == 5
        assert mean == pytest.approx(3.0, abs=1e-6)

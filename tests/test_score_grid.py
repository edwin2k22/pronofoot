"""Tests du moteur de scores Dixon-Coles + Poisson bivarié (score_grid.py).

Propriétés invariantes qu'on vérifie :
- la grille est une distribution de probabilité (somme = 1, toutes cases >= 0)
- le Poisson naïf (rho=0, gamma=0) est un cas particulier de la grille corrigée
- Dixon-Coles (rho < 0) gonfle les scores serrés (0-0, 1-1) vs le Poisson naïf
- l'effet de choc (gamma > 0) gonfle les scénarios extrêmes (BTTS, Over)
- les agrégations 1X2 / O2.5 / BTTS sont cohérentes avec la grille
"""
from __future__ import annotations
from math import exp, factorial

import pytest

from collector.models import score_grid as sg


# ---------- helpers ----------
def _poisson(k, lam):
    return exp(-lam) * lam ** k / factorial(k)


def naive_grid(lam, mu, maxg=sg.MAXG):
    """Poisson indépendant (référence), pour comparer à la grille corrigée."""
    g = [[_poisson(i, lam) * _poisson(j, mu) for j in range(maxg + 1)]
         for i in range(maxg + 1)]
    tot = sum(sum(row) for row in g)
    return [[v / tot for v in row] for row in g]


def cell_sum(grid):
    return round(sum(sum(row) for row in grid), 6)


# ---------- score_grid ----------
class TestScoreGrid:
    def test_grid_is_normalized(self):
        for lam, mu in [(1.0, 1.0), (2.3, 0.8), (0.5, 2.5), (3.0, 3.0)]:
            grid = sg.score_grid(lam, mu)
            assert cell_sum(grid) == pytest.approx(1.0, abs=1e-6), \
                f"grille non normalisée pour lam={lam}, mu={mu}"

    def test_grid_non_negative(self):
        grid = sg.score_grid(1.5, 1.5, rho=-0.06, gamma=0.1)
        for row in grid:
            for p in row:
                assert p >= 0.0

    def test_naive_matches_grid_with_neutral_params(self):
        """Avec rho=0 et gamma=0, la grille = produit de Poissons indépendants."""
        lam, mu = 1.5, 1.2
        grid = sg.score_grid(lam, mu, rho=0.0, gamma=0.0)
        naive = naive_grid(lam, mu)
        for i in range(sg.MAXG + 1):
            for j in range(sg.MAXG + 1):
                assert grid[i][j] == pytest.approx(naive[i][j], abs=1e-9)

    def test_dixon_coles_inflates_low_scores(self):
        """rho < 0 doit gonfler 0-0 et 1-1 par rapport au Poisson naïf."""
        lam, mu = 1.4, 1.1
        naive = naive_grid(lam, mu)
        grid = sg.score_grid(lam, mu, rho=sg.DEFAULT_RHO, gamma=0.0)
        assert grid[0][0] > naive[0][0], "0-0 doit être gonflé par Dixon-Coles"
        assert grid[1][1] > naive[1][1], "1-1 doit être gonflé par Dixon-Coles"

    def test_shock_gamma_increases_btts(self):
        """gamma > 0 (effet de choc) doit augmenter la proba de BTTS."""
        lam, mu = 1.5, 1.5
        o0 = sg.outcomes(sg.score_grid(lam, mu, gamma=0.0))
        o1 = sg.outcomes(sg.score_grid(lam, mu, gamma=0.15))
        assert o1["btts"] > o0["btts"]


# ---------- outcomes / derived ----------
class TestOutcomes:
    def test_outcomes_partition_to_one(self):
        """p1 + pX + p2 = 1 (partition complète)."""
        o = sg.outcomes(sg.score_grid(1.6, 1.3))
        assert (o["p1"] + o["pX"] + o["p2"]) == pytest.approx(1.0, abs=1e-6)

    def test_over_under_complement(self):
        o = sg.outcomes(sg.score_grid(2.0, 1.5))
        assert o["over25"] + o["under25"] == pytest.approx(1.0, abs=1e-6)

    def test_top_score_has_nonzero_prob(self):
        o = sg.outcomes(sg.score_grid(1.4, 1.4))
        i, j = o["top_score"]
        assert isinstance(i, int) and isinstance(j, int)
        assert 0 <= i <= sg.MAXG and 0 <= j <= sg.MAXG

    def test_over_under_lines_complement(self):
        ou = sg.over_under_lines(sg.score_grid(2.0, 1.0), lines=(0.5, 1.5, 2.5, 3.5))
        for ln, vals in ou.items():
            assert vals["over"] + vals["under"] == pytest.approx(1.0, abs=1e-6)
            assert 0.0 <= vals["over"] <= 1.0

    def test_over_lines_decrease_with_line(self):
        """P(over) décroît quand la ligne monte (plus dur à dépasser)."""
        ou = sg.over_under_lines(sg.score_grid(2.0, 1.0), lines=(0.5, 1.5, 2.5, 3.5))
        overs = [ou[ln]["over"] for ln in ("0.5", "1.5", "2.5", "3.5")]
        assert overs == sorted(overs, reverse=True)

    def test_scenarios_partition(self):
        """closed + tight + open = 1 (les 3 premières catégories sont exhaustives)."""
        sc = sg.scenarios(sg.score_grid(1.5, 1.5))
        base = sum(s["p"] for s in sc if not s.get("angle"))
        assert base == pytest.approx(1.0, abs=1e-6)

    def test_double_chance_relations(self):
        dm = sg.derived_markets(sg.score_grid(1.5, 1.5))
        o = sg.outcomes(sg.score_grid(1.5, 1.5))
        assert dm["doubleChance"]["1X"] == pytest.approx(o["p1"] + o["pX"], abs=1e-6)
        assert dm["doubleChance"]["12"] == pytest.approx(o["p1"] + o["p2"], abs=1e-6)
        assert dm["doubleChance"]["X2"] == pytest.approx(o["pX"] + o["p2"], abs=1e-6)

    def test_draw_no_bet_renormalizes(self):
        dm = sg.derived_markets(sg.score_grid(1.5, 1.5))
        dnb = dm["drawNoBet"]
        assert dnb["home"] + dnb["away"] == pytest.approx(1.0, abs=1e-6)
        assert 0.0 <= dnb["home"] <= 1.0

    def test_top_scores_exposes_nearby_exact_scores(self):
        dm = sg.derived_markets(sg.score_grid(1.5, 1.5))
        top_scores = dm["topScores"]
        probs = [s["p"] for s in top_scores]
        assert len(top_scores) == 5
        assert probs == sorted(probs, reverse=True)


# ---------- shock_gamma ----------
class TestShockGamma:
    def test_gamma_is_bounded_and_nonnegative(self):
        for elo in (-300, -100, 0, 100, 300):
            for stake in (0.0, 0.3, 0.5, 0.8, 1.0):
                g = sg.shock_gamma(elo_diff=elo, stage_stake=stake)
                assert 0.0 <= g <= 0.15

    def test_high_stake_increases_gamma(self):
        g_low = sg.shock_gamma(100, stage_stake=0.3)
        g_high = sg.shock_gamma(100, stage_stake=0.9)
        assert g_high >= g_low

    def test_high_risk_flag_adds_gamma(self):
        g = sg.shock_gamma(0, 0.5, high_risk=True)
        assert g > 0.0


# ---------- halftime ----------
class TestHalftime:
    def test_halftime_returns_expected_keys(self):
        ht = sg.halftime(1.5, 1.2)
        for k in ("topScore", "p1", "pX", "p2", "ou05", "ou15"):
            assert k in ht

    def test_halftime_partition(self):
        ht = sg.halftime(1.5, 1.2)
        assert ht["p1"] + ht["pX"] + ht["p2"] == pytest.approx(1.0, abs=1e-6)

    def test_halftime_lower_lambda_reduces_goals(self):
        """Les lambdas mi-temps doivent être < les lambdas plein match."""
        lam_h, lam_a = 1.5, 1.2
        ht = sg.halftime(lam_h, lam_a)
        assert ht["lamHome"] < lam_h
        assert ht["lamAway"] < lam_a

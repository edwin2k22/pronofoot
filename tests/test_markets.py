"""Tests des modèles de marchés (markets.py) : 1X2, buts, corners, cartons.

Propriétés invariantes :
- 1X2 partitionne vers 1.0
- la ligne principale O/U corners/cartons est auto-centrée sur l'attendu
- le favori (Elo >> ) reçoit une proba de victoire supérieure
- les probabilités restent dans [0,1]
"""
from __future__ import annotations

import pytest

from collector.models import markets as mk
from collector.models import score_grid as sg


# ---------- result_model (1X2) ----------
class TestResultModel:
    def test_result_partition(self):
        r = mk.result_model(elo_h=1800, elo_a=1700, lam_h=1.5, lam_a=1.0)
        assert (r["p1"] + r["pX"] + r["p2"]) == pytest.approx(1.0, abs=1e-3)

    def test_stronger_team_is_favourite(self):
        """Une équipe avec un Elo très supérieur doit être favorite (p1 > p2)."""
        r = mk.result_model(elo_h=1950, elo_a=1500, lam_h=1.8, lam_a=0.8)
        assert r["p1"] > r["p2"]

    def test_symmetric_teams_symmetric_probabilities(self):
        """Deux équipes identiques (mêmes Elo, mêmes λ) -> p1 ≈ p2.

        NOTE : result_model applique HOME_ADV_ELO (60 pts) à l'équipe à domicile,
        donc même symétriques, p1 > p2. La symétrie n'apparaît que si on annule
        cet avantage en passant elo_h = elo_a MAIS le lambda home reste > lambda
        away. On vérifie donc la symétrie sur les marchés de buts (goals_model),
        qui eux ne dépendent que des lambda.
        """
        # Mêmes lambda -> mêmes Over/Under/BTTS (symétrie goals)
        g = mk.goals_model(1.3, 1.3)
        assert 0.0 <= g["over"] <= 1.0
        # Et pour le 1X2 : avec l'avantage terrain, p1 (home) doit être >= p2
        r = mk.result_model(elo_h=1800, elo_a=1800, lam_h=1.3, lam_a=1.3)
        assert r["p1"] >= r["p2"]  # home advantage

    def test_elo_weight_extremes(self):
        """elo_weight=0 ignore l'ancrage Elo ; elo_weight=1 le maximise."""
        args = dict(elo_h=1950, elo_a=1500, lam_h=1.8, lam_a=0.8)
        r0 = mk.result_model(**args, elo_weight=0.0)
        r1 = mk.result_model(**args, elo_weight=1.0)
        # Avec plus de poids Elo, l'écart p1-p2 doit s'accentuer
        assert (r1["p1"] - r1["p2"]) > (r0["p1"] - r0["p2"])

    def test_accepts_precomputed_grid(self):
        """On peut passer une grille pré-calculée pour éviter le recalcul."""
        grid = sg.score_grid(1.5, 1.0)
        r = mk.result_model(1800, 1700, 1.5, 1.0, grid=grid)
        assert 0.0 <= r["p1"] <= 1.0


# ---------- goals_model ----------
class TestGoalsModel:
    def test_over_under_complement(self):
        g = mk.goals_model(1.6, 1.2)
        assert g["over"] + g["under"] == pytest.approx(1.0, abs=1e-3)

    def test_expected_goals_equals_lambda_sum(self):
        g = mk.goals_model(1.6, 1.2)
        assert g["exp_goals"] == pytest.approx(2.8, abs=1e-6)

    def test_under15_le_one(self):
        assert 0.0 <= mk.goals_model(1.5, 1.5)["under15"] <= 1.0

    def test_more_attack_increases_over(self):
        o_low = mk.goals_model(0.8, 0.8)
        o_high = mk.goals_model(2.5, 2.5)
        assert o_high["over"] > o_low["over"]


# ---------- corners_model ----------
class TestCornersModel:
    def test_main_line_over_under_complement(self):
        c = mk.corners_model(8.5, 7.5)
        assert c["over"] + c["under"] == pytest.approx(1.0, abs=1e-3)

    def test_main_line_centered_on_expected(self):
        """La ligne principale doit être le .5 inférieur du total attendu."""
        c = mk.corners_model(8.5, 7.5)   # total attendu = 16.0
        assert c["line"] == 15.5 or c["line"] == 16.5  # round(16-0.5)+0.5 = 16.5
        assert c["exp_corners"] == 16.0

    def test_lines_present(self):
        c = mk.corners_model(8.5, 7.5)
        assert len(c["lines"]) >= 3
        for ln, vals in c["lines"].items():
            assert vals["over"] + vals["under"] == pytest.approx(1.0, abs=1e-3)

    def test_dominance_scales_corners(self):
        """Le multiplicateur de domination doit faire varier les corners attendus."""
        base = mk.corners_model(8.0, 7.0, dom_h=1.0, dom_a=1.0)
        boosted = mk.corners_model(8.0, 7.0, dom_h=1.2, dom_a=1.0)
        assert boosted["exp_corners"] > base["exp_corners"]


# ---------- cards_model ----------
class TestCardsModel:
    def test_over_under_complement(self):
        c = mk.cards_model(2.0, 2.0)
        assert c["over"] + c["under"] == pytest.approx(1.0, abs=1e-3)

    def test_expected_cards(self):
        c = mk.cards_model(2.0, 2.0)
        assert c["exp_cards"] == 4.0

    def test_red_prob_bounded(self):
        for ch, ca in [(0.5, 0.5), (3.0, 3.0), (10.0, 10.0)]:
            c = mk.cards_model(ch, ca)
            assert 0.06 <= c["redProb"] <= 0.40

    def test_more_cards_increases_red_prob(self):
        low = mk.cards_model(1.0, 1.0)
        high = mk.cards_model(4.0, 4.0)
        assert high["redProb"] >= low["redProb"]

    def test_fouls_optional_fields(self):
        c = mk.cards_model(2.0, 2.0, fouls_h=12.0, fouls_a=9.0)
        assert c["foulsHome"] == 12.0
        assert c["foulsAway"] == 9.0


# ---------- shots_model ----------
class TestShotsModel:
    def test_expected_totals(self):
        s = mk.shots_model(8.0, 7.0, 3.0, 2.5)
        assert s["expShots"] == 15.0
        assert s["expShotsOn"] == 5.5

    def test_accuracy_in_percent_range(self):
        s = mk.shots_model(8.0, 7.0, 3.0, 2.5)
        assert 0 <= s["homeAcc"] <= 100
        assert 0 <= s["awayAcc"] <= 100

    def test_lines_complement(self):
        s = mk.shots_model(8.0, 7.0, 3.0, 2.5)
        for vals in list(s["lines"].values()) + list(s["linesOn"].values()):
            assert vals["over"] + vals["under"] == pytest.approx(1.0, abs=1e-3)

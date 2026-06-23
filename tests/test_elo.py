"""Tests du moteur Elo évolutif (elo.py).

Propriétés invariantes :
- expected_score est symétrique (P(A bat B) + P(B bat A) = 1, à avantage terrain près)
- K décroît avec l'expérience (anti-overreaction) et est borné par MIN_K
- update_pair conserve la quantité totale d'Elo (jeu à somme nulle, modulo arrondi)
- goal_multiplier augmente avec la marge de victoire
- actual_result borne le signal xG dans [0,1]
"""
from __future__ import annotations

import pytest

from collector.models import elo


class TestExpectedScore:
    def test_equal_teams_close_to_half(self):
        """Deux équipes au même Elo -> ~50/50 (modulo avantage terrain)."""
        e = elo.expected_score(1800, 1800, home_adv=0.0)
        assert e == pytest.approx(0.5, abs=1e-9)

    def test_complement_without_home_adv(self):
        """Sans avantage terrain, P(A) + P(B) = 1."""
        ea = elo.expected_score(1800, 1700, home_adv=0.0)
        eb = elo.expected_score(1700, 1800, home_adv=0.0)
        assert ea + eb == pytest.approx(1.0, abs=1e-9)

    def test_stronger_team_higher_probability(self):
        assert elo.expected_score(1950, 1500) > elo.expected_score(1500, 1950)

    def test_bounded_in_unit_interval(self):
        for a, b in [(1000, 1000), (1300, 2200), (2200, 1300)]:
            assert 0.0 < elo.expected_score(a, b) < 1.0

    def test_home_advantage_increases_home_prob(self):
        e_neutral = elo.expected_score(1800, 1800, home_adv=0.0)
        e_home = elo.expected_score(1800, 1800, home_adv=elo.HOME_ADV_ELO)
        assert e_home > e_neutral


class TestDynamicK:
    def test_k_decreases_with_experience(self):
        k0 = elo.dynamic_k(0)
        k10 = elo.dynamic_k(10)
        k50 = elo.dynamic_k(50)
        assert k0 > k10 > k50

    def test_k_floored_at_min(self):
        """K ne descend jamais sous MIN_K (stabilité)."""
        assert elo.dynamic_k(1000) == elo.MIN_K

    def test_initial_k_equals_base(self):
        assert elo.dynamic_k(0) == elo.BASE_K


class TestActualResult:
    def test_win_draw_loss(self):
        assert elo.actual_result(2, 1, None, None) == 1.0
        assert elo.actual_result(1, 1, None, None) == 0.5
        assert elo.actual_result(0, 3, None, None) == 0.0

    def test_without_xg_uses_score_only(self):
        assert elo.actual_result(2, 0, None, None) == 1.0
        assert elo.actual_result(2, 0, 0.1, 0.1) != 1.0  # blend xG modifie

    def test_xg_result_bounded(self):
        for xgf, xga in [(0.1, 3.0), (3.0, 0.1), (1.5, 1.5)]:
            r = elo.actual_result(1, 1, xgf, xga)
            assert 0.0 <= r <= 1.0

    def test_xg_dominance_reflects_share(self):
        """Le résultat xG doit refléter la part d'xG (xgf / (xgf+xga))."""
        r = elo.actual_result(1, 1, 3.0, 1.0)
        # 1-1 -> score_res = 0.5 ; xg_res = 3/4 = 0.75
        expected = (1 - elo.XG_BLEND) * 0.5 + elo.XG_BLEND * 0.75
        assert r == pytest.approx(expected, abs=1e-9)


class TestGoalMultiplier:
    def test_one_goal_diff_is_neutral(self):
        assert elo.goal_multiplier(1, 0) == 1.0
        assert elo.goal_multiplier(2, 1) == 1.0

    def test_increases_with_margin(self):
        assert elo.goal_multiplier(3, 0) > elo.goal_multiplier(2, 0)
        assert elo.goal_multiplier(5, 0) > elo.goal_multiplier(3, 0)


class TestUpdatePair:
    def test_zero_sum_conservation(self):
        """L'Elo total est conservé (somme nulle), à l'arrondi près.

        NOTE : k_h et k_a peuvent différer (joueurs avec un nombre de matchs
        différent), donc la conservation exacte n'est garantie que si les deux
        équipes ont le même nombre de matchs joués. On teste ce cas.
        """
        eh, ea, gh, ga = 1800.0, 1700.0, 2, 1
        played = 5  # identique pour les deux -> même K -> stricte somme nulle
        new_h, new_a = elo.update_pair(eh, ea, gh, ga, 1.5, 1.2, played, played)
        assert (new_h + new_a) == pytest.approx(eh + ea, abs=0.1)

    def test_winner_gains_elo(self):
        new_h, new_a = elo.update_pair(1800, 1800, 3, 0, None, None, 5, 5)
        assert new_h > 1800
        assert new_a < 1800

    def test_loser_loses_elo(self):
        new_h, new_a = elo.update_pair(1800, 1800, 0, 3, None, None, 5, 5)
        assert new_h < 1800
        assert new_a > 1800

    def test_upset_moves_more_than_expected(self):
        """Une victoire surprise (faible Elo bat fort Elo) doit bouger + l'Elo."""
        # Scénario 1 : favori gagne (attendu)
        nh_fav, _ = elo.update_pair(1900, 1500, 1, 0, None, None, 5, 5)
        gain_fav = nh_fav - 1900
        # Scénario 2 : outsider gagne (surprise)
        nh_out, _ = elo.update_pair(1500, 1900, 1, 0, None, None, 5, 5)
        gain_out = nh_out - 1500
        assert gain_out > gain_fav

from collector import pipeline


def test_manual_lineup_for_france_spain_is_available():
    lineup = pipeline._manual_lineup("France", "Spain")

    assert lineup["source"] == "Barca Blaugranes match thread (XI confirme)"
    assert len(lineup["home_xi"]) == 11
    assert len(lineup["away_xi"]) == 11
    assert "Kylian Mbappe" in lineup["home_xi"]
    assert "Lamine Yamal" in lineup["away_xi"]

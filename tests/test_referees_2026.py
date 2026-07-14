from collector.sources import referees_2026 as refs


def test_semifinal_referees_are_available():
    france_spain = refs.get_referee("France", "Spain")
    england_argentina = refs.get_referee("England", "Argentina")

    assert france_spain["name"] == "Iván Arcides Barton Cisneros"
    assert france_spain["nation"] == "Salvador"
    assert england_argentina["name"] == "Ismail Elfath"
    assert england_argentina["nation"] == "Etats-Unis"

from collector.models import availability as avail


def test_availability_matches_accented_names_with_tactical_suffixes(monkeypatch):
    roster = [
        {"joueur": "Ousmane Dembélé", "poste": "FW"},
        {"joueur": "Kylian Mbappé", "poste": "FW"},
        {"joueur": "Bradley Barcola", "poste": "FW"},
    ]
    xi = [
        "Ousmane Dembélé (AM-R)",
        "Kylian Mbappé (F)",
        "Bradley Barcola (AM-L)",
    ]

    monkeypatch.setattr(avail.bios, "get_bio", lambda name: {"role": "attaquant"})

    res = avail.availability_factor(roster, xi)

    assert res["applied"] is True
    assert res["missing"] == []
    assert res["factor"] == 1.0

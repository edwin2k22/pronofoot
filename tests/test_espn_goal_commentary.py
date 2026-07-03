from collector.sources.espn_stats import _merge_commentary_goals


def test_commentary_goal_fallback_extracts_missing_goals_and_assists():
    comments = [
        {
            "minute": 53,
            "type": "Goal",
            "text": "Goal! Portugal 0, Croatia 1. Ivan Perisic (Croatia) left footed shot from the left side of the box to the centre of the goal.",
        },
        {
            "minute": 68,
            "type": "Penalty - Scored",
            "text": "Goal! Portugal 1, Croatia 1. Cristiano Ronaldo (Portugal) converts the penalty with a right footed shot to the centre of the goal.",
        },
        {
            "minute": 90,
            "type": "Goal - Header",
            "text": "Goal! Portugal 2, Croatia 1. Gonçalo Ramos (Portugal) header from the centre of the box to the bottom right corner. Assisted by Rafael Leão with a cross.",
        },
    ]

    goals = _merge_commentary_goals(
        [{"minute": 53, "team": "Croatia", "player": "Ivan Perisic", "assist": None, "note": None}],
        comments,
    )

    assert [goal["player"] for goal in goals] == ["Ivan Perisic", "Cristiano Ronaldo", "Gonçalo Ramos"]
    assert goals[1]["note"] == "penalty"
    assert goals[2]["assist"] == "Rafael Leão"


def test_commentary_goal_fallback_dedupes_accents_and_punctuation_variants():
    goals = _merge_commentary_goals(
        [
            {"minute": 41, "team": "Saudi Arabia", "player": "Abdulelah Al Amri", "assist": None, "note": None},
            {"minute": 90, "team": "Portugal", "player": "Goncalo Ramos", "assist": None, "note": None},
        ],
        [
            {
                "minute": 41,
                "type": "Goal",
                "text": "Goal! Saudi Arabia 1, Uruguay 0. Abdulelah Al-Amri (Saudi Arabia) header from the centre of the box.",
            },
            {
                "minute": 90,
                "type": "Goal - Header",
                "text": "Goal! Portugal 2, Croatia 1. Gonçalo Ramos (Portugal) header from the centre of the box. Assisted by Rafael Leão with a cross.",
            },
        ],
    )

    assert len(goals) == 2


def test_goal_merge_dedupes_initial_key_events_too():
    goals = _merge_commentary_goals(
        [
            {"minute": 30, "team": "Côte d'Ivoire", "player": "Franck Kessie", "assist": None, "note": None},
            {"minute": 30, "team": "Ivory Coast", "player": "Franck Kessié", "assist": None, "note": None},
            {"minute": 64, "team": "Ivory Coast", "player": "Nicolas Pépé", "assist": None, "note": None},
            {"minute": 64, "team": "Ivory Coast", "player": "Nicolas Pepe", "assist": None, "note": None},
            {"minute": 90, "team": "Bosnia & Herzegovina", "player": "Ermin Mahmic", "assist": None, "note": None},
            {"minute": 90, "team": "Bosnia and Herzegovina", "player": "Ermin Mahmic", "assist": None, "note": None},
        ],
        [],
    )

    assert [goal["player"] for goal in goals] == ["Franck Kessie", "Nicolas Pépé", "Ermin Mahmic"]

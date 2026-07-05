from collector.models import commentary_profiles as cprof
from collector.models import player_props
from collector import pipeline


def test_commentary_profiles_extract_player_shots_assists_and_keeper_saves():
    profiles = cprof.build_profiles({
        "Brazil|Wall FC": {
            "commentary": [
                {
                    "minute": 3,
                    "type": "Shot On Target",
                    "text": "Attempt saved. Vini Jr (Brazil) right footed shot from outside the box is saved in the bottom right corner by Wall Keeper (Wall FC). Assisted by Rodrygo.",
                },
                {
                    "minute": 8,
                    "type": "Shot Blocked",
                    "text": "Attempt blocked. Vini Jr (Brazil) left footed shot from the centre of the box is blocked. Assisted by Neymar.",
                },
                {
                    "minute": 18,
                    "type": "Corner Awarded",
                    "text": "Corner, Brazil. Conceded by Wall Defender.",
                },
            ]
        }
    })

    matchup = cprof.matchup_profile("Brazil", "Wall FC", profiles)
    vini = cprof.player_event_stats(matchup, "Vini Jr")
    rodrygo = cprof.player_event_stats(matchup, "Rodrygo")
    keeper = cprof.player_event_stats(cprof.matchup_profile("Wall FC", "Brazil", profiles), "Wall Keeper")

    assert vini["shots"] == 2
    assert vini["shotsOn"] == 1
    assert vini["shotsBlocked"] == 1
    assert rodrygo["createdShots"] == 1
    assert keeper["saves"] == 1
    assert matchup["team"]["cornersFor"] == 1
    assert matchup["opponent"]["cornersAllowed"] == 1


def test_matchup_factor_reduces_shot_props_against_tight_defense():
    events = {
        "Brazil|Open FC": {
            "commentary": [
                {"minute": i, "type": "Shot Off Target", "text": "Attempt missed. Vini Jr (Brazil) right footed shot from outside the box misses to the right."}
                for i in range(1, 7)
            ]
        },
        "Open FC|Brazil": {
            "commentary": [
                {"minute": i, "type": "Shot Off Target", "text": "Attempt missed. Open Striker (Open FC) right footed shot from outside the box misses to the right."}
                for i in range(1, 7)
            ]
        },
        "Wall FC|Other": {"commentary": []},
        "Other|Wall FC": {"commentary": []},
    }
    profiles = cprof.build_profiles(events)
    vs_open = cprof.matchup_profile("Brazil", "Open FC", profiles)
    vs_wall = cprof.matchup_profile("Brazil", "Wall FC", profiles)
    assert vs_wall["factors"]["shots"] < vs_open["factors"]["shots"]

    roster = [{"joueur": "Vini Jr", "poste": "FW", "statut": "Titulaire"}]
    stats = {"Vini Jr": {"minutes": 180, "tirs": 8, "tirs_cadres": 3, "statut": "Titulaire", "matchs_2026": 2}}
    open_props = player_props.compute("Brazil", roster, 2.0, 0.6, stats_team=stats, event_profile=vs_open, exp_team_shots=None)
    wall_props = player_props.compute("Brazil", roster, 2.0, 0.6, stats_team=stats, event_profile=vs_wall, exp_team_shots=None)

    assert wall_props["matchup"]["shotFactor"] < open_props["matchup"]["shotFactor"]
    assert wall_props["shotProps"][0]["expected"] < open_props["shotProps"][0]["expected"]


def test_preserved_prediction_gets_matchup_player_props(monkeypatch):
    match = {
        "home": "Brazil",
        "away": "Wall FC",
        "homeXG": 1.8,
        "awayXG": 0.7,
        "prediction": {
            "shots": {"home": 12, "away": 6, "homeOn": 4, "awayOn": 2},
            "cards": {"foulsHome": 10, "foulsAway": 14},
            "playerProps": {"home": {"scorers": []}, "away": {"scorers": []}},
        },
    }
    squads = {
        "Brazil": [{"joueur": "Vini Jr", "poste": "FW", "statut": "Titulaire"}],
        "Wall FC": [{"joueur": "Wall Striker", "poste": "FW", "statut": "Titulaire"}],
    }

    monkeypatch.setattr(pipeline, "_load_squads", lambda: squads)
    monkeypatch.setattr(pipeline, "_load_player_stats", lambda: {})
    monkeypatch.setattr(
        pipeline.cprof,
        "matchup_profile",
        lambda team, opp: {
            "sample": 1,
            "team": {"shotsFor": 10, "shotsOnFor": 3, "foulsCommitted": 11},
            "opponent": {},
            "players": {},
            "factors": {"shots": 0.8, "shotsOn": 0.9, "fouls": 1.1},
        },
    )

    pipeline._refresh_player_props_snapshot(match)

    home_props = match["prediction"]["playerProps"]["home"]
    assert home_props["shotProps"][0]["name"] == "Vini Jr"
    assert home_props["matchup"]["shotFactor"] == 0.8

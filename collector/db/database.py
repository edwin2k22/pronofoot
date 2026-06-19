"""
Point 6 — Base locale (SQLite, zéro dépendance).

Robuste, fichier unique (collector/db/pronofoot.db), transactionnel.
Stocke : équipes + ratings évolutifs, matchs (calendrier + résultats réels),
stats post-match (xG/tirs/corners/cartons), et l'historique des ratings (audit).

C'est la mémoire du système : on ne dépend plus du réseau à chaque fois, et on
garde la trace de TOUTE mise à jour (point 4) pour pouvoir rejouer / déboguer.
"""
from __future__ import annotations
import sqlite3, os, datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "pronofoot.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS teams (
    name          TEXT PRIMARY KEY,
    elo           REAL NOT NULL DEFAULT 1500,      -- rating évolutif (point 2 & 4)
    fifa_prior    REAL,                            -- prior FIFA/Elo de départ
    matches_played INTEGER NOT NULL DEFAULT 0,
    -- moyennes évolutives (mises à jour par shrinkage, point 5)
    gf_avg        REAL DEFAULT 1.35,
    ga_avg        REAL DEFAULT 1.35,
    xg_avg        REAL DEFAULT 1.35,
    xga_avg       REAL DEFAULT 1.35,
    corners_avg   REAL DEFAULT 5.0,
    cards_avg     REAL DEFAULT 2.0,
    updated_at    TEXT
);

CREATE TABLE IF NOT EXISTS matches (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    competition   TEXT,
    stage         TEXT,
    utc_date      TEXT,
    home          TEXT NOT NULL,
    away          TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'SCHEDULED', -- SCHEDULED / FINISHED
    -- résultat réel (rempli après le match, point 4)
    home_goals    INTEGER,
    away_goals    INTEGER,
    home_xg       REAL,
    away_xg       REAL,
    home_shots    INTEGER,
    away_shots    INTEGER,
    home_corners  INTEGER,
    away_corners  INTEGER,
    home_cards    INTEGER,
    away_cards    INTEGER,
    events_json   TEXT,                                -- buteurs/cartons/MOTM (JSON)
    processed     INTEGER NOT NULL DEFAULT 0,        -- 1 si déjà intégré aux ratings
    UNIQUE(competition, home, away, utc_date)
);

-- audit : chaque variation de rating est tracée (point 4 & 5)
CREATE TABLE IF NOT EXISTS rating_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    team        TEXT NOT NULL,
    match_id    INTEGER,
    elo_before  REAL,
    elo_after   REAL,
    reason      TEXT,
    ts          TEXT
);

-- joueurs RÉELS sélectionnés CDM 2026 (identité ; stats agrégées remplies au fil des matchs)
CREATE TABLE IF NOT EXISTS players (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    team          TEXT NOT NULL,
    number        INTEGER,
    pos           TEXT,
    dob           TEXT,
    age           INTEGER,
    matches_2026  INTEGER NOT NULL DEFAULT 0,   -- nb matchs 2026 joués (0 = stats N/D)
    minutes_2026  INTEGER NOT NULL DEFAULT 0,
    -- totaux cumulés sur la CDM 2026 (NULL/0 tant que pas joué)
    goals INTEGER DEFAULT 0, assists INTEGER DEFAULT 0,
    shots INTEGER DEFAULT 0, shots_on INTEGER DEFAULT 0,
    xg REAL DEFAULT 0, xa REAL DEFAULT 0,
    passes INTEGER DEFAULT 0, prog_passes INTEGER DEFAULT 0,
    tackles INTEGER DEFAULT 0, interceptions INTEGER DEFAULT 0,
    blocks INTEGER DEFAULT 0, clearances INTEGER DEFAULT 0,
    pressures INTEGER DEFAULT 0, recoveries INTEGER DEFAULT 0,
    fouls INTEGER DEFAULT 0, offsides INTEGER DEFAULT 0,
    cards TEXT DEFAULT '',
    UNIQUE(name, team)
);

-- stats joueur par MATCH 2026 (rempli par player_ingest quand un match est dispo)
CREATE TABLE IF NOT EXISTS player_match_stats (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    player_name TEXT, team TEXT, match_ref TEXT,
    minutes INTEGER, goals INTEGER, assists INTEGER,
    shots INTEGER, shots_on INTEGER, xg REAL, xa REAL,
    passes INTEGER, prog_passes INTEGER, tackles INTEGER,
    interceptions INTEGER, blocks INTEGER, clearances INTEGER,
    pressures INTEGER, recoveries INTEGER, fouls INTEGER,
    offsides INTEGER, cards TEXT,
    UNIQUE(player_name, team, match_ref)
);
"""


def connect(path: str = DB_PATH) -> sqlite3.Connection:
    # timeout=30 : attend si la base est verrouillée plutôt que d'échouer tout de suite
    conn = sqlite3.connect(path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # ── Robustesse écritures/lectures concurrentes (live polling + serveur web) ──
    # WAL : lecteurs et écrivain ne se bloquent plus mutuellement (anti-corruption
    # silencieuse lors des pics d'activité les jours de match).
    conn.execute("PRAGMA journal_mode = WAL")
    # busy_timeout : en cas de verrou bref, on patiente 30 s au lieu de planter.
    conn.execute("PRAGMA busy_timeout = 30000")
    # synchronous=NORMAL : sûr avec WAL, bien plus rapide que FULL pour le polling.
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def init_db(path: str = DB_PATH) -> sqlite3.Connection:
    conn = connect(path)
    conn.executescript(SCHEMA)
    # migrations légères (colonnes ajoutées après coup)
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(matches)").fetchall()}
    if "events_json" not in cols:
        conn.execute("ALTER TABLE matches ADD COLUMN events_json TEXT")
    if "home_shots_on" not in cols:
        conn.execute("ALTER TABLE matches ADD COLUMN home_shots_on INTEGER")
    if "away_shots_on" not in cols:
        conn.execute("ALTER TABLE matches ADD COLUMN away_shots_on INTEGER")
    if "team_stats_json" not in cols:
        conn.execute("ALTER TABLE matches ADD COLUMN team_stats_json TEXT")
    # moyennes évolutives de tirs / tirs cadrés par équipe (point : pronos tirs)
    tcols = {r["name"] for r in conn.execute("PRAGMA table_info(teams)").fetchall()}
    if "shots_avg" not in tcols:
        conn.execute("ALTER TABLE teams ADD COLUMN shots_avg REAL DEFAULT 12.0")
    if "shots_on_avg" not in tcols:
        conn.execute("ALTER TABLE teams ADD COLUMN shots_on_avg REAL DEFAULT 4.2")
    if "shots_against_avg" not in tcols:
        conn.execute("ALTER TABLE teams ADD COLUMN shots_against_avg REAL DEFAULT 12.0")
    if "shots_on_against_avg" not in tcols:
        conn.execute("ALTER TABLE teams ADD COLUMN shots_on_against_avg REAL DEFAULT 4.2")
    if "possession_avg" not in tcols:
        conn.execute("ALTER TABLE teams ADD COLUMN possession_avg REAL DEFAULT 50.0")
    # minute de jeu live réelle (ex "56'") fournie par ESPN pendant un match en cours
    if "live_clock" not in cols:
        conn.execute("ALTER TABLE matches ADD COLUMN live_clock TEXT")
    conn.commit()
    return conn


def now() -> str:
    return datetime.datetime.utcnow().isoformat(timespec="seconds")


# ---------- équipes ----------
def upsert_team(conn, name, elo=None, fifa_prior=None):
    row = conn.execute("SELECT name FROM teams WHERE name=?", (name,)).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO teams(name, elo, fifa_prior, updated_at) VALUES (?,?,?,?)",
            (name, elo if elo is not None else 1500,
             fifa_prior if fifa_prior is not None else elo, now()))
    elif elo is not None:
        conn.execute("UPDATE teams SET elo=?, updated_at=? WHERE name=?", (elo, now(), name))


def get_team(conn, name):
    return conn.execute("SELECT * FROM teams WHERE name=?", (name,)).fetchone()


def all_teams(conn):
    return conn.execute("SELECT * FROM teams ORDER BY elo DESC").fetchall()


# ---------- matchs ----------
def upsert_match(conn, competition, stage, utc_date, home, away, status="SCHEDULED"):
    # ne JAMAIS écraser un match déjà LIVE / HT / FINISHED lors d'un re-seed :
    # on ne met le statut à jour que s'il était encore SCHEDULED.
    conn.execute("""
        INSERT INTO matches(competition, stage, utc_date, home, away, status)
        VALUES (?,?,?,?,?,?)
        ON CONFLICT(competition, home, away, utc_date) DO UPDATE SET
            status = CASE WHEN matches.status='SCHEDULED' THEN excluded.status
                          ELSE matches.status END
    """, (competition, stage, utc_date, home, away, status))


def record_result(conn, match_id, **stats):
    """Enregistre le résultat réel + stats post-match (point 4)."""
    cols = ["home_goals", "away_goals", "home_xg", "away_xg", "home_shots",
            "away_shots", "home_corners", "away_corners", "home_cards", "away_cards"]
    sets = ", ".join(f"{c}=?" for c in cols if c in stats)
    vals = [stats[c] for c in cols if c in stats]
    conn.execute(f"UPDATE matches SET {sets}, status='FINISHED' WHERE id=?",
                 (*vals, match_id))


def unprocessed_finished(conn):
    """Matchs terminés pas encore intégrés aux ratings."""
    return conn.execute(
        "SELECT * FROM matches WHERE status='FINISHED' AND processed=0 ORDER BY utc_date"
    ).fetchall()


def mark_processed(conn, match_id):
    conn.execute("UPDATE matches SET processed=1 WHERE id=?", (match_id,))


def log_rating(conn, team, match_id, before, after, reason):
    conn.execute("""INSERT INTO rating_history(team, match_id, elo_before, elo_after, reason, ts)
                    VALUES (?,?,?,?,?,?)""", (team, match_id, before, after, reason, now()))


# ---------- joueurs (effectifs 2026) ----------
def upsert_player(conn, name, team, number=None, pos=None, dob=None, age=None):
    conn.execute("""
        INSERT INTO players(name, team, number, pos, dob, age) VALUES (?,?,?,?,?,?)
        ON CONFLICT(name, team) DO UPDATE SET
            number=excluded.number, pos=excluded.pos, dob=excluded.dob, age=excluded.age
    """, (name, team, number, pos, dob, age))


def players_by_team(conn, team):
    return conn.execute(
        "SELECT * FROM players WHERE team=? ORDER BY number", (team,)).fetchall()


def all_player_teams(conn):
    return [r["team"] for r in conn.execute(
        "SELECT DISTINCT team FROM players ORDER BY team").fetchall()]


def add_player_match(conn, **st):
    """Ajoute une ligne de stats joueur pour un match 2026 + met à jour les cumuls."""
    cols = ["player_name", "team", "match_ref", "minutes", "goals", "assists",
            "shots", "shots_on", "xg", "xa", "passes", "prog_passes", "tackles",
            "interceptions", "blocks", "clearances", "pressures", "recoveries",
            "fouls", "offsides", "cards"]
    vals = [st.get(c) for c in cols]
    try:
        conn.execute(f"""INSERT INTO player_match_stats({','.join(cols)})
                         VALUES ({','.join('?'*len(cols))})""", vals)
    except Exception:
        return False  # déjà ingéré (UNIQUE)
    # cumul sur players
    conn.execute("""
        UPDATE players SET
          matches_2026=matches_2026+1,
          minutes_2026=minutes_2026+?, goals=goals+?, assists=assists+?,
          shots=shots+?, shots_on=shots_on+?, xg=xg+?, xa=xa+?,
          passes=passes+?, prog_passes=prog_passes+?, tackles=tackles+?,
          interceptions=interceptions+?, blocks=blocks+?, clearances=clearances+?,
          pressures=pressures+?, recoveries=recoveries+?, fouls=fouls+?,
          offsides=offsides+?,
          cards = TRIM(cards || ' ' || ?)
        WHERE name=? AND team=?
    """, (st.get("minutes",0), st.get("goals",0), st.get("assists",0),
          st.get("shots",0), st.get("shots_on",0), st.get("xg",0), st.get("xa",0),
          st.get("passes",0), st.get("prog_passes",0), st.get("tackles",0),
          st.get("interceptions",0), st.get("blocks",0), st.get("clearances",0),
          st.get("pressures",0), st.get("recoveries",0), st.get("fouls",0),
          st.get("offsides",0), st.get("cards","") or "",
          st.get("player_name"), st.get("team")))
    return True

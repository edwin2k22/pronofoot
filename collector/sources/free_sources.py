"""
Free-source registry and audit guard for PronoFoot.

The app is allowed to use public/free endpoints, static open datasets and local
files. This module does not judge data quality; it makes the "0 euro" contract
explicit and testable.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Iterable


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(ROOT, "collector", "data")


@dataclass(frozen=True)
class FreeSource:
    id: str
    label: str
    role: str
    refresh: str
    reliability: str
    limitation: str
    url: str


FREE_SOURCES: tuple[FreeSource, ...] = (
    FreeSource(
        id="openfootball",
        label="openfootball",
        role="Calendrier, groupes, resultats officiels quand publies",
        refresh="batch",
        reliability="stable",
        limitation="Pas de live fin ni de stats joueurs",
        url="https://github.com/openfootball/worldcup.json",
    ),
    FreeSource(
        id="espn-public",
        label="ESPN public",
        role="Score live, minute, stats, events, compos et arbitres quand disponibles",
        refresh="live",
        reliability="good",
        limitation="Endpoint non contractuel, couverture variable selon match",
        url="https://site.api.espn.com/",
    ),
    FreeSource(
        id="smarkets-public",
        label="Smarkets public",
        role="Cotes alternatives sans cle pour BTTS/corners/cartons si exposees",
        refresh="batch",
        reliability="fragile",
        limitation="API publique non officielle pour notre usage, peut changer",
        url="https://api.smarkets.com/",
    ),
    FreeSource(
        id="fotmob-manual",
        label="FotMob projected XI",
        role="XI projetes saisis/cachees avant XI officiel",
        refresh="manual",
        reliability="medium",
        limitation="Scraping automatique non branche; source a verifier match par match",
        url="https://www.fotmob.com/",
    ),
    FreeSource(
        id="football-data-uk",
        label="Football-Data.co.uk",
        role="Historique resultats et cotes pour backtests/calibration",
        refresh="batch",
        reliability="stable",
        limitation="Pas adapte au live ni aux compos",
        url="https://www.football-data.co.uk/",
    ),
    FreeSource(
        id="statsbomb-open-data",
        label="StatsBomb open-data",
        role="Event data gratuit pour entrainement avance",
        refresh="research",
        reliability="stable",
        limitation="Competition coverage limitee, pas live",
        url="https://github.com/statsbomb/open-data",
    ),
    FreeSource(
        id="clubelo",
        label="ClubElo",
        role="Ratings de force equipe en fallback/recherche",
        refresh="batch",
        reliability="stable",
        limitation="Club-centric; utile surtout comme inspiration/calibration",
        url="https://clubelo.com/",
    ),
)


PAID_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("API-Football", re.compile(r"\b(API_FOOTBALL|api-football|apifootball)\b", re.I)),
    ("Sportmonks", re.compile(r"\b(SPORTMONKS|sportmonks)\b", re.I)),
    ("RapidAPI key", re.compile(r"\b(RAPIDAPI_KEY|X-RapidAPI-Key)\b", re.I)),
    ("The Odds API", re.compile(r"\b(THE_ODDS_API|ODDS_API_KEY|the-odds-api)\b", re.I)),
    ("Bet365 API", re.compile(r"\b(BET365_KEY|bet365api|bet365_api)\b", re.I)),
)

SCAN_TARGETS = (
    "collector",
    "assets",
    "tests",
    "scripts",
    ".github",
    "deploy",
    "requirements.txt",
    "requirements-dev.txt",
    "Dockerfile",
)

SKIP_DIRS = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    "cache",
    "data",
    "htmlcov",
    "node_modules",
}

TEXT_EXTS = {
    ".bat",
    ".cfg",
    ".css",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".ps1",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".yml",
    ".yaml",
}


def _iter_files(root: str, targets: Iterable[str] = SCAN_TARGETS) -> Iterable[str]:
    for target in targets:
        path = os.path.join(root, target)
        if os.path.isfile(path):
            yield path
            continue
        if not os.path.isdir(path):
            continue
        for dirpath, dirnames, filenames in os.walk(path):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for name in filenames:
                ext = os.path.splitext(name)[1].lower()
                if ext in TEXT_EXTS:
                    yield os.path.join(dirpath, name)


def scan_for_paid_dependencies(root: str = ROOT) -> list[dict[str, object]]:
    hits: list[dict[str, object]] = []
    for path in _iter_files(root):
        rel = os.path.relpath(path, root).replace("\\", "/")
        if rel == "collector/sources/free_sources.py":
            continue
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except OSError:
            continue
        in_docstring = False
        for lineno, line in enumerate(lines, start=1):
            stripped = line.strip()
            triple_quotes = stripped.count('"""') + stripped.count("'''")
            if in_docstring:
                if triple_quotes % 2:
                    in_docstring = False
                continue
            if stripped.startswith(('"""', "'''")):
                if triple_quotes % 2:
                    in_docstring = True
                continue
            code_line = line.split("#", 1)[0]
            for label, pattern in PAID_PATTERNS:
                if pattern.search(code_line):
                    hits.append({"file": rel, "line": lineno, "source": label})
    return hits


def prediction_source_summary(path: str | None = None) -> dict[str, object]:
    path = path or os.path.join(DATA, "predictions.json")
    try:
        with open(path, encoding="utf-8") as f:
            matches = json.load(f)
    except (OSError, ValueError):
        matches = []

    source_counts: Counter[str] = Counter()
    official_xi = 0
    projected_xi = 0
    referees = 0
    odds = 0
    live_capable = 0

    for match in matches:
        prediction = match.get("prediction") or {}
        source_counts.update(match.get("sources") or [])
        if prediction.get("officialLineups"):
            official_xi += 1
        if prediction.get("projectedLineups"):
            projected_xi += 1
        if (prediction.get("referee") or {}).get("name"):
            referees += 1
        if match.get("odd1") or match.get("oddOver") or match.get("oddBTTS_Yes"):
            odds += 1
        if any(src.startswith("ESPN") for src in match.get("sources") or []):
            live_capable += 1

    return {
        "matches": len(matches),
        "sources": dict(sorted(source_counts.items())),
        "officialLineups": official_xi,
        "projectedLineups": projected_xi,
        "referees": referees,
        "odds": odds,
        "liveCapable": live_capable,
    }


def manifest() -> dict[str, object]:
    return {
        "mode": "free-only",
        "contract": "No paid API key is required to build, refresh or deploy the app.",
        "sources": [asdict(source) for source in FREE_SOURCES],
        "paidAudit": {
            "patterns": [label for label, _ in PAID_PATTERNS],
            "scope": list(SCAN_TARGETS),
        },
    }


def report_json() -> dict[str, object]:
    hits = scan_for_paid_dependencies()
    return {
        **manifest(),
        "paidDependencyHits": hits,
        "predictionSummary": prediction_source_summary(),
    }


def print_text_report() -> None:
    payload = report_json()
    print("PronoFoot free-only source audit")
    print(f"Mode: {payload['mode']}")
    print(f"Contract: {payload['contract']}\n")
    print("Sources gratuites autorisees:")
    for source in payload["sources"]:
        print(f"  - {source['label']}: {source['role']} ({source['reliability']})")
    hits = payload["paidDependencyHits"]
    print("\nAudit dependances payantes:")
    if not hits:
        print("  OK - aucune dependance a cle payante detectee dans le code actif.")
    else:
        for hit in hits:
            print(f"  FAIL - {hit['source']} dans {hit['file']}:{hit['line']}")
    summary = payload["predictionSummary"]
    print("\nCouverture predictions actuelles:")
    print(f"  Matchs: {summary['matches']}")
    print(f"  Cotes: {summary['odds']}")
    print(f"  Arbitres: {summary['referees']}")
    print(f"  XI officiels: {summary['officialLineups']}")
    print(f"  XI projetes: {summary['projectedLineups']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit free-only data sources")
    parser.add_argument("--json", action="store_true", help="print JSON payload")
    parser.add_argument("--audit", action="store_true", help="exit 1 if paid dependency hits exist")
    args = parser.parse_args(argv)

    payload = report_json()
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print_text_report()

    if args.audit and payload["paidDependencyHits"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

import asyncio
import subprocess
import sys
import unittest
from pathlib import Path

import uvicorn

from app.domains.football_v2 import FootballBootstrapService, PickemService
from app.domains.football_v2.utils import configure_logging
from app.domains.football_v2.workers.finished_matches_worker import (
    main as finished_matches_worker_main,
)
from app.domains.football_v2.workers.live_matches_worker import main as live_matches_worker_main

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# API server commands
def api_main() -> None:
    """Deployed run"""
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)

def api_dev_main() -> None:
    """Dev run"""
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

# Project commands
def run_tests() -> None:
    """Lanza los tests"""
    suite = unittest.defaultTestLoader.discover("tests")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)

def check_backend() -> None:
    commands = [
        [sys.executable, "-m", "ruff", "check", "."],
        [sys.executable, "-m", "ruff", "format", "--check", "."],
        [sys.executable, "-m", "unittest", "discover", "tests"],
    ]

    for command in commands:
        result = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
        if result.returncode != 0:
            raise SystemExit(result.returncode)

# Workers
def run_football_live_worker() -> None:
    live_matches_worker_main()

def run_football_post_match_worker() -> None:
    finished_matches_worker_main()
    
# Jobs
def sync_football_data() -> None:
    configure_logging()

    stats = asyncio.run(FootballBootstrapService().run())
    for key, value in stats.items():
        print(f"{key}: {value}")

def score_pickem_entry() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: uv run score-pickem <contest_id>")
    PickemService().score_contest(int(sys.argv[1]))

def sync_pickem_players_entry() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: uv run sync-pickem-players <contest_id>")
    import asyncio

    stats = asyncio.run(PickemService().sync_squads_from_fotmob(int(sys.argv[1])))
    for key, value in stats.model_dump().items():
        print(f"{key}: {value}")

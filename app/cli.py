import logging
import subprocess
import sys
import unittest
from pathlib import Path

import uvicorn

from app.domains.football_v2 import FootballBootstrapService
from app.domains.football_v2.worker import main as worker_football_main

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def api_main() -> None:
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)


def api_dev_main() -> None:
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)


def test_entry() -> None:
    suite = unittest.defaultTestLoader.discover("tests")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)


def check_entry() -> None:
    commands = [
        [sys.executable, "-m", "ruff", "check", "."],
        [sys.executable, "-m", "ruff", "format", "--check", "."],
        [sys.executable, "-m", "unittest", "discover", "tests"],
    ]

    for command in commands:
        result = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
        if result.returncode != 0:
            raise SystemExit(result.returncode)


def bootstrap_football_entry() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    import asyncio

    stats = asyncio.run(FootballBootstrapService().run())
    for key, value in stats.items():
        print(f"{key}: {value}")


def worker_football_entry() -> None:
    worker_football_main()

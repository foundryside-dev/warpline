from __future__ import annotations

import subprocess
import sys
from os import environ

import heddle


def test_package_has_version() -> None:
    assert heddle.__version__ == "1.0.0"


def test_cli_version() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "heddle.cli", "--version"],
        check=True,
        env={**environ, "PYTHONPATH": "src"},
        text=True,
        stdout=subprocess.PIPE,
    )
    assert completed.stdout.strip() == "heddle 1.0.0"

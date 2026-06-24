from __future__ import annotations

import subprocess
import sys
from importlib.metadata import version
from os import environ

import warpline


def test_version_derives_from_package_metadata() -> None:
    # __version__ is the installed package metadata version (single source of
    # truth), not a hand-maintained literal. This is the regression guard for
    # the 1.1.2 release where a hardcoded __version__ went stale.
    assert warpline.__version__ == version("warpline")


def test_cli_version_matches_package_version() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "warpline.cli", "--version"],
        check=True,
        env={**environ, "PYTHONPATH": "src"},
        text=True,
        stdout=subprocess.PIPE,
    )
    assert completed.stdout.strip() == f"warpline {version('warpline')}"

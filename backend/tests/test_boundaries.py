"""The module boundaries from SPEC §17.3 exist and are enforced."""

from __future__ import annotations

import subprocess
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]

EXPECTED_MODULES = [
    "core",
    "db",
    "auth",
    "items",
    "moderation",
    "rating",
    "matchmaking",
    "battles",
    "comparisons",
    "rankings",
    "public",
    "admin",
    "analytics",
    "worker",
    "api",
]


def test_every_module_exists() -> None:
    """Created up front so nobody has to decide where code goes later."""
    pkg = BACKEND_ROOT / "src/pickone"
    for module in EXPECTED_MODULES:
        assert (pkg / module / "__init__.py").is_file(), f"missing package: {module}"


def test_import_linter_contracts_hold() -> None:
    """rating/ stays pure; matchmaking/ never learns to compute a rating.

    These contracts are trivially true today because the packages are empty.
    That is exactly why they are wired up now — the failure they prevent
    happens in M3 and M4, when it is expensive to unpick.
    """
    result = subprocess.run(
        ["lint-imports", "--config", str(BACKEND_ROOT / "pyproject.toml")],
        capture_output=True,
        text=True,
        cwd=BACKEND_ROOT,
    )
    assert result.returncode == 0, result.stdout + result.stderr

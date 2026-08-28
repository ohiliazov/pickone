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
    "analytics",
    "worker",
    "api",
]


def test_every_module_exists() -> None:
    pkg = BACKEND_ROOT / "src/pickone"
    for module in EXPECTED_MODULES:
        assert (pkg / module / "__init__.py").is_file(), f"missing package: {module}"


def test_import_linter_contracts_hold() -> None:
    result = subprocess.run(
        ["lint-imports", "--config", str(BACKEND_ROOT / "pyproject.toml")],
        capture_output=True,
        text=True,
        cwd=BACKEND_ROOT,
    )
    assert result.returncode == 0, result.stdout + result.stderr

"""Repeat offline checks and save exact exit codes and outputs under examples/validation."""

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    output = ROOT / "examples" / "validation"
    output.mkdir(parents=True, exist_ok=True)
    commands = {
        "pytest": ["-m", "pytest", "-q"],
        "ruff": ["-m", "ruff", "check", "src", "tests", "scripts"],
        "format": ["-m", "ruff", "format", "--check", "src", "tests", "scripts"],
        "sources": ["-m", "sciagg", "sources", "--json"],
        "h-index": ["-m", "sciagg", "h-index", "10", "8", "5", "4", "3", "1", "--json"],
        "demo": ["-m", "sciagg", "demo"],
        "raw-hashes": ["scripts/rebuild_database.py", "--verify-only", "--use-validated-vak-json"],
    }
    runs = []
    for name, args in commands.items():
        completed = subprocess.run(
            [sys.executable, *args],
            cwd=ROOT,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=180,
        )
        (output / f"{name}.txt").write_text(completed.stdout + completed.stderr, encoding="utf-8")
        runs.append(
            {"name": name, "args": args, "exit_code": completed.returncode, "output_file": f"{name}.txt"}
        )
        print(f"{name}: exit {completed.returncode}")
    (output / "results.json").write_text(
        json.dumps(
            {"verified_at": datetime.now(UTC).isoformat(), "python": sys.version, "checks": runs}, indent=2
        ),
        encoding="utf-8",
    )
    return 1 if any(x["exit_code"] for x in runs) else 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_engine_exits_2_when_killswitch_present(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[1]
    data_dir = repo / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    ks = data_dir / "KILL_SWITCH"
    ks.write_text("", encoding="utf-8")

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    # Run engine in the repo so relative paths resolve.
    p = subprocess.run(
        [sys.executable, "-m", "algonovax", "engine"],
        cwd=str(repo),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=20,
    )

    # Clean up so local dev isn't impacted if someone runs tests.
    try:
        ks.unlink(missing_ok=True)
    except Exception:
        pass

    assert p.returncode == 2, f"expected exit=2, got {p.returncode}\n--- output ---\n{p.stdout}"

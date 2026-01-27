from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_engine_killswitch_exits_2(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    ks = root / "data" / "KILL_SWITCH"
    ks.parent.mkdir(parents=True, exist_ok=True)
    if ks.exists():
        ks.unlink()

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    p = subprocess.Popen(
        [sys.executable, "-u", "-m", "algonovax", "engine"],
        cwd=str(root),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        # let it start
        for _ in range(20):
            if p.poll() is not None:
                break
            if ks.exists():
                break
        ks.touch()
        rc = p.wait(timeout=10)
    finally:
        try:
            p.kill()
        except Exception:
            pass

    assert rc == 2

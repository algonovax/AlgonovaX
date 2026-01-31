from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_engine_rejects_paper_plus_live(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[1]

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["EXCHANGE"] = "paper"
    env["LIVE_TRADING_ENABLED"] = "1"
    env["PAPER_TRADING_ENABLED"] = "1"

    # prevent long-running loop if it somehow got past guards
    env["KILL_SWITCH_PATH"] = "./data/KILL_SWITCH"
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "KILL_SWITCH").write_text("", encoding="utf-8")

    code = (
        "import sys; sys.path.insert(0, r'%s'); "
        "import runpy; "
        "sys.argv=['algonovax','engine']; "
        "runpy.run_module('algonovax', run_name='__main__')"
    ) % repo.as_posix()

    p = subprocess.run(
        [sys.executable, "-u", "-c", code],
        cwd=str(tmp_path),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=10,
    )

    assert p.returncode != 0
    assert "EXCHANGE=paper is incompatible" in p.stdout or "requires EXCHANGE=kraken" in p.stdout

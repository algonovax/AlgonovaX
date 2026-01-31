from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_engine_exits_2_when_kill_switch_present(tmp_path: Path) -> None:
    # run engine from a temp repo-root so relative ./data/KILL_SWITCH resolves
    root = tmp_path
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "data" / "KILL_SWITCH").write_text("", encoding="utf-8")

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["KILL_SWITCH_PATH"] = "./data/KILL_SWITCH"

    # Ensure module import works: run from real repo but set cwd to tmp root
    # Use -c to add repo to sys.path explicitly.
    repo = Path(__file__).resolve().parents[1]
    code = (
        "import sys; sys.path.insert(0, r'%s'); "
        "import runpy; "
        "sys.argv=['algonovax','engine']; "
        "runpy.run_module('algonovax', run_name='__main__')"
    ) % repo.as_posix()

    p = subprocess.run(
        [sys.executable, "-u", "-c", code],
        cwd=str(root),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=10,
    )

    assert p.returncode == 2, f"expected exit=2 got {p.returncode}\n---\n{p.stdout}"

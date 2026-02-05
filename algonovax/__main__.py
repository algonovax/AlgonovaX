from __future__ import annotations

import argparse
import os
import sys
import traceback


def _cmd_engine(argv: list[str]) -> int:
    # Lazy import so GUI deps don't affect engine runs
    from algonovax.engine.engine import run_engine

    return int(run_engine())


def _cmd_gui(argv: list[str]) -> int:
    try:
        import uvicorn  # type: ignore
    except Exception as e:
        sys.stderr.write(
            f"FAIL: GUI requires uvicorn. Install: pip install 'uvicorn'\ncause: {e}\n"
        )
        return 2

    host = os.getenv("ALGONOVAX_HOST", "0.0.0.0")
    try:
        port = int(os.getenv("ALGONOVAX_PORT", "8000"))
    except Exception:
        port = 8000
from ui.gui import app  # type: ignore

    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    p = argparse.ArgumentParser(prog="algonovax")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("engine", help="run trading engine")
    sub.add_parser("gui", help="run GUI server (uvicorn)")

    ns, rest = p.parse_known_args(argv)

    try:
        if ns.cmd == "engine":
            return _cmd_engine(rest)
        if ns.cmd == "gui":
            return _cmd_gui(rest)
        return 2
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        sys.stderr.write("TRACEBACK:\n" + traceback.format_exc() + "\n")
        sys.stderr.write(f"FAIL: {e}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

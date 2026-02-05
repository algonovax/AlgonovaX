from __future__ import annotations

import argparse
import sys


def _cmd_gui(rest: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="algonovax gui", add_help=True)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8790)
    ns = ap.parse_args(rest)

    try:
        import uvicorn  # type: ignore
    except Exception as e:
        print("FAIL: GUI requires uvicorn. Install: pip install 'uvicorn'\n" f"cause: {e}")
        return 2

    from algonovax.webapp import app  # type: ignore
    uvicorn.run(app, host=ns.host, port=ns.port, log_level="info")
    return 0


def _cmd_engine(rest: list[str]) -> int:
    # Delegate to existing engine CLI module
    try:
        from algonovax.engine.engine import main as engine_main  # type: ignore
    except Exception as e:
        print("FAIL: engine module missing/broken")
        raise

    try:
        rc = engine_main(rest)  # expects argv-like list
        return int(rc) if rc is not None else 0
    except SystemExit as e:
        return int(e.code) if e.code is not None else 0


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    ap = argparse.ArgumentParser(prog="algonovax", add_help=True)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("gui", help="run GUI server (uvicorn)")
    sub.add_parser("engine", help="run engine (delegates to algonovax.engine.engine)")

    ns, rest = ap.parse_known_args(argv)

    if ns.cmd == "gui":
        return _cmd_gui(rest)
    if ns.cmd == "engine":
        return _cmd_engine(rest)

    ap.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

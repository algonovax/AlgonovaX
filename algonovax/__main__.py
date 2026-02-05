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


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    ap = argparse.ArgumentParser(prog="algonovax", add_help=True)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("gui", help="run GUI server (uvicorn)")

    ns, rest = ap.parse_known_args(argv)

    if ns.cmd == "gui":
        return _cmd_gui(rest)

    ap.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

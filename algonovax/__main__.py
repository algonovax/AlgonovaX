from __future__ import annotations

import argparse


def main() -> int:
    p = argparse.ArgumentParser(prog="algonovax")
    sub = p.add_subparsers(dest="cmd", required=True)

    serve = sub.add_parser("serve", help="Run FastAPI server")
    serve.add_argument("--host", default=None)
    serve.add_argument("--port", type=int, default=None)

    sub.add_parser("engine", help="Run engine loop (blocking)")

    args = p.parse_args()

    if args.cmd == "serve":
        from algonovax.config import load_settings
        import uvicorn

        s = load_settings()
        host = args.host or s.host
        port = args.port or s.port
        uvicorn.run("algonovax.app:create_app", factory=True, host=host, port=port)
        return 0

    if args.cmd == "engine":
        from algonovax.config import load_settings
        from algonovax.engine import run_loop

        s = load_settings()
        run_loop(s)
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())

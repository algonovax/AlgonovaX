from __future__ import annotations

import argparse
import os
import sys

import uvicorn

from .config import load_settings
from .engine import run_loop


def _apply_overrides(settings, host: str | None, port: int | None):
    """
    Return a settings object with host and/or port values overridden when provided.
    
    If both `host` and `port` are None, the original `settings` object is returned unchanged.
    
    Parameters:
        settings: The settings dataclass instance to base the result on.
        host (str | None): Optional host override; when provided, replaces the `host` value in the returned settings.
        port (int | None): Optional port override; when provided, replaces the `port` value in the returned settings.
    
    Returns:
        A new settings instance (same type as `settings`) with `host` and `port` replaced by the provided overrides when present; other fields are preserved.
    """
    if host is None and port is None:
        return settings
    # dataclass is frozen; rebuild safely
    return type(settings)(
        env=settings.env,
        paper_trading=settings.paper_trading,
        live_trading=settings.live_trading,
        exchange=settings.exchange,
        symbol=settings.symbol,
        timeframe=settings.timeframe,
        host=host or settings.host,
        port=port or settings.port,
        log_level=settings.log_level,
        kill_switch_path=settings.kill_switch_path,
        max_daily_loss_usd=settings.max_daily_loss_usd,
        max_open_positions=settings.max_open_positions,
        kraken_api_key=settings.kraken_api_key,
        kraken_api_secret=settings.kraken_api_secret,
    )


def main() -> int:
    """
    Parse command-line arguments and dispatch the requested subcommand to either start the ASGI server or run the engine loop, returning a process exit code.
    
    Supports two subcommands:
    - "serve": loads settings (with optional --host and --port overrides) and starts the ASGI application via uvicorn.
    - "engine": loads settings and runs the engine loop (blocking).
    
    Returns:
        int: Exit code where
            0   = successful execution of the chosen subcommand,
            2   = unknown or missing subcommand,
            130 = interrupted by KeyboardInterrupt,
            1   = fatal error occurred (logged to stderr).
    """
    p = argparse.ArgumentParser(prog="algonovax")
    sub = p.add_subparsers(dest="cmd", required=True)

    serve = sub.add_parser("serve", help="Run FastAPI server")
    serve.add_argument("--host", default=None)
    serve.add_argument("--port", type=int, default=None)

    eng = sub.add_parser("engine", help="Run engine loop (blocking)")

    args = p.parse_args()

    try:
        settings = load_settings()
        if args.cmd == "serve":
            settings = _apply_overrides(settings, args.host, args.port)

            # If systemd is already running, this will fail with EADDRINUSE.
            uvicorn.run(
                "algonovax.app:create_app",
                factory=True,
                host=settings.host,
                port=settings.port,
                log_level=settings.log_level.lower(),
            )
            return 0

        if args.cmd == "engine":
            run_loop(settings)
            return 0

        return 2
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        print(f"[FATAL] {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
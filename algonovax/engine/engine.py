from __future__ import annotations
import traceback
from pathlib import Path
from typing import Any
import threading


def _candle_dict(c: Any) -> dict[str, Any]:
    if isinstance(c, dict):
        return c
    try:
        d = getattr(c, "__dict__", None)
        if isinstance(d, dict):
            return d
    except Exception:
        pass
    try:
        from dataclasses import asdict

        return asdict(c)
    except Exception:
        return {"_raw": repr(c)}


# SAFE_INTENT_ATTR_HELPER
def _safe_attr(obj: object, name: str, default=None):
    try:
        return getattr(obj, name)
    except Exception:
        return default


# TB_ON_ALL_FATAL
def _tb() -> str:
    try:
        return traceback.format_exc()
    except Exception:
        return ""


KILL_SWITCH_PATH = Path("data/KILL_SWITCH")
STATE_PATH = "data/state.json"


# =========================
# ENTRYPOINTS (DO NOT CYCLE)
# =========================
def run_engine(stop_evt: threading.Event | None = None) -> int:
    """CLI entrypoint: python -m algonovax engine"""
    from algonovax.config import load_settings
    from algonovax.engine.core import run_loop as settings_run_loop

    settings = load_settings()
    # ENGINE_CONFIG_GUARDS
    # Safety: refuse contradictory modes.
    if settings.live_trading:
        if settings.exchange != "kraken":
            raise RuntimeError("LIVE_TRADING_ENABLED=1 requires EXCHANGE=kraken")
    if settings.exchange == "paper":
        if not settings.paper_trading:
            raise RuntimeError("EXCHANGE=paper requires PAPER_TRADING_ENABLED=1")
        if settings.live_trading:
            raise RuntimeError("EXCHANGE=paper is incompatible with LIVE_TRADING_ENABLED=1")
    try:
        try:
            settings_run_loop(settings, stop_evt)
        except TypeError:
            settings_run_loop(settings)
        return 0
    except SystemExit:
        # preserve explicit exit codes from core loop (e.g., kill switch)
        raise
    except KeyboardInterrupt:
        return 130
def run_loop(cfg=None, strategy=None) -> int:
    """Back-compat shim. Ignore args; env/config driven."""
    return int(run_engine())


def run(cfg, strategy) -> int:
    """Back-compat API. Ignore args; env/config driven."""
    return int(run_engine())


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for `python -m algonovax engine`.

    Must exist for tests + __main__.py. Must preserve exit code 2 for killswitch.
    """
    import traceback

    try:
        # Prefer config-driven settings if available.
        settings = None
        try:
            from algonovax.config import load_settings  # type: ignore
            settings = load_settings()
        except Exception:
            # If config isn't available/compatible, fall back to calling run_engine directly.
            settings = None

        try:
            if settings is not None:
                try:
                    return int(run_engine(settings))  # type: ignore[arg-type]
                except TypeError:
                    return int(run_engine())  # type: ignore[call-arg]
            return int(run_engine())  # type: ignore[call-arg]
        except SystemExit as e:
            # Preserve SystemExit codes (killswitch expects 2)
            try:
                return int(e.code)  # type: ignore[arg-type]
            except Exception:
                return 1
    except Exception:
        traceback.print_exc()
        return 1


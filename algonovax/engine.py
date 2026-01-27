"""Compatibility shim.

Keep this module as a narrow import layer for stale imports.
Real logic lives in algonovax.engine.core.
"""

from __future__ import annotations

from algonovax.engine.core import run_loop, run_once

__all__ = ["run_loop", "run_once"]

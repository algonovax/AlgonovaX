from __future__ import annotations

from typing import Callable, Dict

import pandas as pd

from .types import Signal

StrategyFn = Callable[[pd.DataFrame], Signal]

_REGISTRY: Dict[str, StrategyFn] = {}


def register(name: str, fn: StrategyFn) -> None:
    _REGISTRY[name] = fn


def get(name: str) -> StrategyFn:
    if name not in _REGISTRY:
        raise KeyError(
            f"Unknown strategy: {name}. Available: {sorted(_REGISTRY.keys())}"
        )
    return _REGISTRY[name]


def available() -> list[str]:
    return sorted(_REGISTRY.keys())

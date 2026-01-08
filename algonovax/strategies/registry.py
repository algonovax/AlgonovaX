from __future__ import annotations

from typing import Callable, Dict

import pandas as pd

from .types import Signal

StrategyFn = Callable[[pd.DataFrame], Signal]

_REGISTRY: Dict[str, StrategyFn] = {}


def register(name: str, fn: StrategyFn) -> None:
    """
    Register a strategy callable under the given name.
    
    If a strategy is already registered under the same name, it will be overwritten.
    
    Parameters:
        name (str): Key used to store and later retrieve the strategy.
        fn (StrategyFn): Callable that accepts a pandas DataFrame and returns a Signal.
    """
    _REGISTRY[name] = fn


def get(name: str) -> StrategyFn:
    """
    Retrieve a registered strategy by name.
    
    Parameters:
        name (str): The registry key for the desired strategy.
    
    Returns:
        strategy (StrategyFn): The strategy callable associated with `name`.
    
    Raises:
        KeyError: If `name` is not in the registry; the error message includes available strategy names.
    """
    if name not in _REGISTRY:
        raise KeyError(f"Unknown strategy: {name}. Available: {sorted(_REGISTRY.keys())}")
    return _REGISTRY[name]


def available() -> list[str]:
    """
    List all strategy names currently registered in the module.
    
    Returns:
        list[str]: Sorted list of registered strategy names.
    """
    return sorted(_REGISTRY.keys())
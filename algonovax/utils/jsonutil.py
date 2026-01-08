from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any


def _default(o: Any):
    # dataclasses
    """
    Produce a JSON-serializable representation of an arbitrary object.
    
    Attempts, in order: convert dataclasses to dict via asdict; use an Enum's `value`; call a `to_dict()` method if present; return the object's `__dict__` if available; otherwise return `str(o)`.
    
    Parameters:
        o (Any): Object to convert.
    
    Returns:
        Any: A representation suitable for JSON serialization — typically a dict (from dataclass, `to_dict()`, or `__dict__`), an Enum value, or a string fallback.
    """
    if is_dataclass(o):
        return asdict(o)

    # enums (Signal is probably one)
    if isinstance(o, Enum):
        return o.value

    # common patterns
    if hasattr(o, "to_dict") and callable(getattr(o, "to_dict")):
        return o.to_dict()

    # fallback: try public attrs
    if hasattr(o, "__dict__"):
        return o.__dict__

    return str(o)


def dumps(obj: Any, **kwargs) -> str:
    """
    Serialize an object to a JSON-formatted string using enhanced handling for dataclasses, Enum members, objects with a `to_dict` method, and objects with `__dict__`.
    
    Parameters:
    	obj (Any): The Python object to serialize.
    	**kwargs: Additional keyword arguments forwarded to `json.dumps` (e.g., `indent`, `sort_keys`).
    
    Returns:
    	JSON string: A JSON-formatted string representation of `obj`.
    """
    return json.dumps(
        obj,
        default=_default,
        ensure_ascii=False,
        **kwargs,
    )


def dump(obj: Any, path: str | Path, **kwargs) -> None:
    """
    Write an object as JSON to a file at the given path, creating parent directories if necessary.
    
    Parameters:
        obj (Any): Object to serialize to JSON.
        path (str | Path): Filesystem path to write the JSON file to; parent directories will be created.
        **kwargs: Additional keyword arguments forwarded to the JSON serializer (e.g., `indent`, `sort_keys`).
    
    Notes:
        The file is written using UTF-8 encoding. By default the JSON is pretty-printed with an indentation of 2 spaces and keys sorted.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        dumps(obj, indent=2, sort_keys=True, **kwargs),
        encoding="utf-8",
    )
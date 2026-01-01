from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any


def _default(o: Any):
    # dataclasses
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
    return json.dumps(
        obj,
        default=_default,
        ensure_ascii=False,
        **kwargs,
    )


def dump(obj: Any, path: str | Path, **kwargs) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        dumps(obj, indent=2, sort_keys=True, **kwargs),
        encoding="utf-8",
    )

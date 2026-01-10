from __future__ import annotations

import json
import os
import time
from typing import Any

INTENTS_PATH = os.path.join(
    os.environ.get("ALGONOVAX_ROOT") or os.path.expanduser("~/AlgonovaX"),
    "data",
    "intents.json",
)
STATE_PATH = os.path.join(
    os.environ.get("ALGONOVAX_ROOT") or os.path.expanduser("~/AlgonovaX"),
    "data",
    "intents_state.json",
)


def _read_json(path: str) -> Any:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True)


def _now() -> int:
    return int(time.time())


def pop_new_intents(max_items: int = 20) -> list[dict]:
    """
    Reads intents.json and returns only intents not yet processed.
    State is tracked by last_ts + last_idx.
    """
    data = _read_json(INTENTS_PATH) or {}
    intents = data.get("intents", []) or []

    st = _read_json(STATE_PATH) or {"last_ts": 0, "last_idx": 0}
    last_ts = int(st.get("last_ts", 0))
    last_idx = int(st.get("last_idx", 0))

    out: list[dict] = []
    for i, it in enumerate(intents):
        ts = int(it.get("ts", 0))
        if ts < last_ts:
            continue
        if ts == last_ts and i <= last_idx:
            continue
        out.append(it)

    out = out[:max_items]

    if out:
        newest = out[-1]
        new_ts = int(newest.get("ts", _now()))
        new_idx = intents.index(newest)
        _write_json(
            STATE_PATH, {"last_ts": new_ts, "last_idx": new_idx, "updated": _now()}
        )

    return out

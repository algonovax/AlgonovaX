from __future__ import annotations

import json
import os
import time
from typing import Any

INTENTS_PATH = os.path.expanduser("~/projects/AlgonovaX/data/intents.json")
STATE_PATH = os.path.expanduser("~/projects/AlgonovaX/data/intents_state.json")


def _read_json(path: str) -> Any:
    """
    Read and parse a JSON file at the given filesystem path.
    
    Parameters:
        path (str): Path to the JSON file to read.
    
    Returns:
        The parsed JSON object, or `None` if the file does not exist.
    """
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: str, obj: Any) -> None:
    """
    Write a Python object to a JSON file, creating parent directories if they do not exist.
    
    Parameters:
        path (str): Filesystem path to write the JSON file to.
        obj (Any): JSON-serializable Python object to write. The output is encoded as UTF-8, formatted with an indentation of 2 spaces, and object keys are sorted.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True)


def _now() -> int:
    """
    Get the current time as an integer UNIX timestamp.
    
    Returns:
        int: Current time in seconds since the UNIX epoch.
    """
    return int(time.time())


def pop_new_intents(max_items: int = 20) -> list[dict]:
    """
    Selects unprocessed intents from the intents store and advances the recorded state.
    
    Reads intents from INTENTS_PATH, filters those with a timestamp/index greater than the stored state in STATE_PATH, limits the result to at most `max_items`, updates the stored state to the newest returned intent, and returns the selected intents.
    
    Parameters:
        max_items (int): Maximum number of intents to return.
    
    Returns:
        list[dict]: Intent objects that are newer than the stored state, limited to `max_items`.
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
        _write_json(STATE_PATH, {"last_ts": new_ts, "last_idx": new_idx, "updated": _now()})

    return out
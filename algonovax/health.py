from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .config import Settings

def health_payload(settings: Settings) -> dict[str, Any]:
    # Never include secrets
    data = asdict(settings)
    data["kraken_api_key"] = None
    data["kraken_api_secret"] = None
    return {"ok": True, "settings": data}

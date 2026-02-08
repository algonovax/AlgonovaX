from __future__ import annotations
import socket
from typing import Any

_ORIG_GETADDRINFO = socket.getaddrinfo
_ENABLED = False

def force_ipv4() -> None:
    global _ENABLED
    if _ENABLED:
        return

    def _getaddrinfo(host: Any, port: Any, family: int = 0, type: int = 0, proto: int = 0, flags: int = 0):
        return _ORIG_GETADDRINFO(host, port, socket.AF_INET, type, proto, flags)

    socket.getaddrinfo = _getaddrinfo  # type: ignore[assignment]
    _ENABLED = True

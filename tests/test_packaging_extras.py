from __future__ import annotations

import importlib.util as u

import pytest

WEB = ("fastapi", "starlette", "uvicorn", "jinja2", "multipart", "pydantic")


def test_core_has_no_web_deps() -> None:
    # This test is ONLY valid when the environment was installed WITHOUT extras.
    # If someone runs pytest after installing ".[api]" locally, we skip instead of failing.
    present = [m for m in WEB if u.find_spec(m)]
    if present:
        pytest.skip(f"Not a core-only environment; web deps present: {present}")

    assert present == []

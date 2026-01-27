from __future__ import annotations

import importlib.util as u

WEB = ("fastapi", "starlette", "uvicorn", "jinja2", "multipart", "pydantic")


def test_api_extra_has_web_deps() -> None:
    missing = [m for m in WEB if not u.find_spec(m)]
    assert missing == [], f"API extra missing deps: {missing}"

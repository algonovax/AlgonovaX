from __future__ import annotations

import os
import importlib.util as u

import pytest

WEB = ("fastapi", "starlette", "uvicorn", "jinja2", "multipart", "pydantic")


def test_api_extra_has_web_deps() -> None:
    # Only enforce in the "api" install job.
    if os.getenv("ALGONOVAX_EXPECT_API") != "1":
        pytest.skip("API deps not expected in this environment (set ALGONOVAX_EXPECT_API=1 in api job)")

    missing = [m for m in WEB if not u.find_spec(m)]
    assert missing == [], f"API extra missing deps: {missing}"

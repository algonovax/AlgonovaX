from __future__ import annotations

import json
import os

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import RedirectResponse, FileResponse, JSONResponse

app = FastAPI(title="AlgoNovaX")

# --- Mount GUI router ---
try:
    from ui.gui import router as gui_router

    app.include_router(gui_router)
except Exception as e:
    raise RuntimeError(f"Failed to mount GUI router: {e}") from e


@app.get("/")
def _root():
    return RedirectResponse(url="/ui", status_code=307)


# --- favicon hardening (never 500) ---
@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    try:
        p = os.path.join(os.path.dirname(__file__), "static", "favicon.ico")
        if os.path.exists(p):
            return FileResponse(p)
        return Response(status_code=204)
    except Exception:
        return Response(status_code=204)


# --- backtest last/output endpoints ---
_BASE = os.environ.get("ALGONOVAX_ROOT") or os.path.expanduser("~/AlgonovaX")
_BACKTEST_LAST = os.path.join(_BASE, "data", "backtest_last.json")
_BACKTEST_OUT = os.path.join(_BASE, "logs", "backtests", "backtest.out")


@app.get("/api/backtest/last")
def api_backtest_last():
    try:
        if not os.path.exists(_BACKTEST_LAST):
            raise HTTPException(status_code=404, detail="backtest_last.json not found")
        with open(_BACKTEST_LAST, "r", encoding="utf-8") as f:
            return JSONResponse(content=json.load(f))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"failed reading backtest_last.json: {e}"
        )


@app.get("/api/backtest/output")
def api_backtest_output(tail: int = 200):
    try:
        tail = max(1, min(int(tail), 5000))
        if not os.path.exists(_BACKTEST_OUT):
            return Response(content="", media_type="text/plain")
        with open(_BACKTEST_OUT, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()[-tail:]
        return Response(content="".join(lines), media_type="text/plain")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"failed reading backtest output: {e}"
        )

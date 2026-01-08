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
    """
    Redirect requests to the web UI at /ui.
    
    Returns:
        redirect (RedirectResponse): A response that redirects the client to '/ui' with HTTP status 307.
    """
    return RedirectResponse(url="/ui", status_code=307)

# --- favicon hardening (never 500) ---
@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    """
    Serve the application's favicon when available; otherwise return no content.
    
    Returns:
        FileResponse when the favicon file exists; Response with status code 204 when the file is missing or an error occurs.
    """
    try:
        p = os.path.join(os.path.dirname(__file__), "static", "favicon.ico")
        if os.path.exists(p):
            return FileResponse(p)
        return Response(status_code=204)
    except Exception:
        return Response(status_code=204)

# --- backtest last/output endpoints ---
_BASE = os.path.expanduser("~/projects/AlgonovaX")
_BACKTEST_LAST = os.path.join(_BASE, "data", "backtest_last.json")
_BACKTEST_OUT = os.path.join(_BASE, "logs", "backtests", "backtest.out")

@app.get("/api/backtest/last")
def api_backtest_last():
    """
    Fetches the contents of backtest_last.json and returns them as a JSONResponse.
    
    Returns:
        JSONResponse: Parsed JSON content of backtest_last.json.
    
    Raises:
        HTTPException: If the file is not found (status 404) or if reading/parsing fails (status 500).
    """
    try:
        if not os.path.exists(_BACKTEST_LAST):
            raise HTTPException(status_code=404, detail="backtest_last.json not found")
        with open(_BACKTEST_LAST, "r", encoding="utf-8") as f:
            return JSONResponse(content=json.load(f))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"failed reading backtest_last.json: {e}")

@app.get("/api/backtest/output")
def api_backtest_output(tail: int = 200):
    """
    Retrieve the tail of the backtest output log as plain text.
    
    Parameters:
        tail (int): Number of lines to return from the end of the backtest output. Values are clamped to the range 1..5000.
    
    Returns:
        Response: A plain-text HTTP response whose body is the last `tail` lines of the backtest output file, or an empty string if the output file does not exist.
    
    Raises:
        HTTPException: With status code 500 if an error occurs while reading the backtest output file.
    """
    try:
        tail = max(1, min(int(tail), 5000))
        if not os.path.exists(_BACKTEST_OUT):
            return Response(content="", media_type="text/plain")
        with open(_BACKTEST_OUT, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()[-tail:]
        return Response(content="".join(lines), media_type="text/plain")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"failed reading backtest output: {e}")
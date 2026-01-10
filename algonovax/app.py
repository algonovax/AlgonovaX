from __future__ import annotations

import logging
import threading
from fastapi import FastAPI

from .config import load_settings
from .health import health_payload
from .logging import configure_logging
from .engine import run_loop

log = logging.getLogger("algonovax.api")


def create_app() -> FastAPI:
    settings = load_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="AlgoNovaX", version="0.1.0")

    @app.get("/health")
    def health() -> dict:
        return health_payload(settings)

    @app.post("/engine/start")
    def engine_start() -> dict:
        # Simple threaded start for now; later replace with a proper worker/supervisor.
        t = threading.Thread(target=run_loop, args=(settings,), daemon=True)
        t.start()
        log.info("engine_thread_started")
        return {"ok": True}

    return app

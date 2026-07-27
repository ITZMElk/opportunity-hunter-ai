from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.dashboard import router as dashboard_router
from app.db import database_is_connected, init_db
from app.logging_config import configure_logging
from app.pipeline.run import run_pipeline
from app.scheduler import scheduler_status, start_scheduler, stop_scheduler
from app.sources.unstop_source import UnstopSource

configure_logging()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    UnstopSource(get_settings().unstop_api_url).warn_if_using_fixture()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="Opportunity Hunter AI", version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(dashboard_router)


@app.get("/health")
def health() -> dict[str, str | int]:
    """Railway-friendly liveness/readiness details without exposing secrets."""
    settings = get_settings()
    database_connected = database_is_connected()
    return {
        "status": "ok" if database_connected else "degraded",
        "scheduler": scheduler_status(),
        "database": "connected" if database_connected else "unavailable",
        "rss_sources": len(settings.rss_feed_urls),
    }


@app.post("/run-now")
def run_now() -> dict[str, int | bool]:
    """Run one cycle immediately, useful for local testing."""
    try:
        return run_pipeline()
    except Exception as error:
        raise HTTPException(status_code=500, detail="Pipeline run failed; check server logs") from error

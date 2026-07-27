from __future__ import annotations

import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.config import get_settings
from app.db import engine
from app.pipeline.run import run_pipeline

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler(timezone="Asia/Kolkata")
_LOCK_KEY = 8_845_210
_scheduler_lock_connection: Connection | None = None


def scheduled_run() -> None:
    logger.info("Running Scheduled Check at %s", datetime.now().astimezone().isoformat())
    try:
        result = run_pipeline()
        logger.info("Finished Scheduled Check: %s", result)
    except Exception:
        logger.exception("Scheduled pipeline failed")


def _acquire_scheduler_lock() -> bool:
    """Use a PostgreSQL advisory lock so only one Railway replica schedules jobs."""
    global _scheduler_lock_connection
    if engine.dialect.name != "postgresql":
        return True
    try:
        connection = engine.connect()
        acquired = bool(connection.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": _LOCK_KEY}).scalar())
        if acquired:
            _scheduler_lock_connection = connection
            return True
        connection.close()
        logger.warning("Scheduler not started: another application instance owns the PostgreSQL scheduler lock")
        return False
    except Exception:
        logger.exception("Scheduler not started: unable to acquire PostgreSQL scheduler lock")
        return False


def _release_scheduler_lock() -> None:
    global _scheduler_lock_connection
    if _scheduler_lock_connection is None:
        return
    try:
        _scheduler_lock_connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": _LOCK_KEY})
    finally:
        _scheduler_lock_connection.close()
        _scheduler_lock_connection = None


def start_scheduler() -> None:
    if scheduler.running:
        return
    if not _acquire_scheduler_lock():
        return
    interval_minutes = get_settings().schedule_interval_minutes
    scheduler.add_job(
        scheduled_run,
        "interval",
        minutes=interval_minutes,
        id="opportunity-pipeline",
        replace_existing=True,
    )
    scheduler.start()
    job = scheduler.get_job("opportunity-pipeline")
    logger.info("Starting Scheduler; interval=%s minutes, next run=%s", interval_minutes, job.next_run_time if job else "unknown")


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
    _release_scheduler_lock()


def scheduler_status() -> str:
    return "running" if scheduler.running else "stopped"

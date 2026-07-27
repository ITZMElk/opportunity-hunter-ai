"""Application logging with console and daily rotated file output."""
from __future__ import annotations

import logging
import json
from datetime import datetime, timezone
from logging.handlers import TimedRotatingFileHandler

from app.config import PROJECT_ROOT, get_settings


class JsonFormatter(logging.Formatter):
    """Small dependency-free JSON formatter suitable for Railway log ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    settings = get_settings()
    log_directory = PROJECT_ROOT / "logs"
    log_directory.mkdir(exist_ok=True)
    formatter = JsonFormatter()
    root = logging.getLogger()
    root.setLevel(settings.log_level)
    if root.handlers:
        return
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    daily_file = TimedRotatingFileHandler(log_directory / "opportunity-hunter.log", when="midnight", backupCount=14, encoding="utf-8")
    daily_file.setFormatter(formatter)
    root.addHandler(console)
    root.addHandler(daily_file)

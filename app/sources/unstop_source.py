from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import requests

from app.http import create_http_session
from app.sources.base import RawItem, Source, register_source

logger = logging.getLogger(__name__)
FIXTURE_PATH = Path(__file__).with_name("unstop_fixture.json")


@register_source
class UnstopSource(Source):
    """Normalizes a JSON endpoint or the bundled fixture into RawItem objects.

    This intentionally uses only a configured API endpoint; it does not scrape Unstop.
    """

    def __init__(self, api_url: str | None, timeout_seconds: float = 15) -> None:
        self.api_url = api_url
        self.timeout_seconds = timeout_seconds
        self.http = create_http_session()

    @classmethod
    def from_settings(cls, settings: object) -> "UnstopSource":
        return cls(settings.unstop_api_url)

    def warn_if_using_fixture(self) -> None:
        """Make the non-live fallback visible as soon as the server starts."""
        if not self.api_url:
            logger.warning("WARNING: Unstop source is using static test data — no live feed available.")

    def _load_payload(self) -> Any:
        if not self.api_url:
            return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        response = self.http.get(self.api_url, timeout=self.timeout_seconds)
        response.raise_for_status()
        return response.json()

    def fetch(self) -> list[RawItem]:
        try:
            payload = self._load_payload()
            rows = payload.get("data", payload.get("opportunities", payload)) if isinstance(payload, dict) else payload
            if not isinstance(rows, list):
                logger.warning("Unstop-style endpoint returned no list of opportunities")
                return []
            return [self._to_raw_item(row) for row in rows if isinstance(row, dict)]
        except Exception:
            logger.exception("Could not fetch Unstop-style source")
            return []

    @staticmethod
    def _to_raw_item(row: dict[str, Any]) -> RawItem:
        organizer = row.get("organizer") or row.get("company") or row.get("organization") or "unknown"
        return RawItem(
            title=str(row.get("title") or row.get("name") or "Untitled opportunity"),
            organizer=str(organizer),
            description=str(row.get("description") or row.get("summary") or ""),
            url=row.get("url") or row.get("link"),
            source="unstop",
        )

from __future__ import annotations

import logging
from collections.abc import Sequence

import feedparser

from app.http import create_http_session
from app.sources.base import RawItem, Source, register_source

logger = logging.getLogger(__name__)


@register_source
class RssSource(Source):
    """Fetches all configured, permitted RSS or Atom feeds."""

    def __init__(self, feed_urls: Sequence[str]) -> None:
        self.feed_urls = tuple(feed_urls)
        self.http = create_http_session()

    @classmethod
    def from_settings(cls, settings: object) -> "RssSource | None":
        return cls(settings.rss_feed_urls) if settings.rss_feed_urls else None

    def fetch(self) -> list[RawItem]:
        if not self.feed_urls:
            logger.info("RSS_FEED_URLS is not configured; skipping RSS sources")
            return []
        items: list[RawItem] = []
        for feed_url in self.feed_urls:
            items.extend(self._fetch_one(feed_url))
        return items

    def _fetch_one(self, feed_url: str) -> list[RawItem]:
        try:
            response = self.http.get(feed_url, timeout=(5, 20))
            response.raise_for_status()
            feed = feedparser.parse(response.content)
            if feed.bozo:
                logger.warning("RSS/Atom feed %s reported a parsing issue: %s", feed_url, feed.bozo_exception)
            if not feed.entries:
                logger.warning("RSS/Atom feed %s returned no entries; skipping it", feed_url)
            return [
                RawItem(
                    title=entry.get("title", "Untitled opportunity"),
                    organizer=self._organizer(entry, feed),
                    description=entry.get("summary", entry.get("description", "")),
                    url=entry.get("link"),
                    source="rss",
                )
                for entry in feed.entries
                if entry.get("title")
            ]
        except Exception:
            logger.exception("Could not fetch RSS/Atom feed %s", feed_url)
            return []

    @staticmethod
    def _organizer(entry: object, feed: object) -> str:
        """Use the entry author, then the feed title, without assuming feedparser types."""
        author = entry.get("author")
        if author:
            return str(author)
        source = entry.get("source")
        if source and source.get("title"):
            return str(source["title"])
        return str(feed.feed.get("title", "unknown"))

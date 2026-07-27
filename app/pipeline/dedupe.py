from __future__ import annotations

import hashlib
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import Opportunity
from app.sources.base import RawItem


def normalized_hash(title: str, organizer: str) -> str:
    """Return a stable hash for case/whitespace-insensitive duplicate detection."""
    value = "|".join(re.sub(r"\s+", " ", part).strip().casefold() for part in (title, organizer))
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def is_new_item(session: Session, item: RawItem) -> bool:
    item_hash = normalized_hash(item.title, item.organizer)
    return session.scalar(select(Opportunity.id).where(Opportunity.dedupe_hash == item_hash)) is None


def store_new_item(session: Session, item: RawItem) -> Opportunity | None:
    if not is_new_item(session, item):
        return None
    opportunity = Opportunity(
        dedupe_hash=normalized_hash(item.title, item.organizer),
        source=item.source,
        raw_url=item.url,
        raw_text=item.description,
        title=item.title,
        organizer=item.organizer,
    )
    session.add(opportunity)
    session.flush()
    return opportunity

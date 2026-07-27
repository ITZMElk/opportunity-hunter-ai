from __future__ import annotations

from app.db import Opportunity


def rank_recommended(items: list[Opportunity]) -> list[Opportunity]:
    """Keep qualifying items and order the strongest matches first."""
    return sorted(
        (item for item in items if item.recommended and (item.suitability_score or 0) >= 70),
        key=lambda item: item.suitability_score or 0,
        reverse=True,
    )

from __future__ import annotations

import logging

from app.config import get_settings
from app.db import Opportunity, get_session
from app.pipeline.dedupe import store_new_item
from app.pipeline.llm_analyze import GeminiAnalyzer
from app.pipeline.notify import send_digest
from app.pipeline.rank import rank_recommended
from app.sources.base import RawItem, discover_sources

logger = logging.getLogger(__name__)


def _apply_analysis(opportunity: Opportunity, analysis: object) -> None:
    data = analysis.model_dump()
    opportunity.title = data["title"]
    opportunity.organizer = data["organizer"]
    opportunity.opportunity_type = data["type"]
    opportunity.deadline = data["deadline"]
    opportunity.eligibility = data["eligibility"]
    opportunity.location = data["location"]
    opportunity.cost = data["cost"]
    opportunity.prize_or_benefit = data["prize_or_benefit"]
    opportunity.suitability_score = data["score"]
    opportunity.suitability_reasons = " | ".join(data["reasoning"])
    opportunity.skills_matched = " | ".join(data["skills_matched"])
    opportunity.missing_skills = " | ".join(data["missing_skills"])
    opportunity.deadline_urgency = data["deadline_urgency"]
    opportunity.resume_value = data["resume_value"]
    opportunity.difficulty = data["difficulty"]
    opportunity.recommended = data["recommendation"]
    opportunity.analyzed = True


def run_pipeline() -> dict[str, int | bool]:
    """Fetch, deduplicate, analyze, rank, and notify for one pipeline cycle."""
    settings = get_settings()
    sources = discover_sources(settings)
    raw_items: list[RawItem] = [item for source in sources for item in source.fetch()]
    analyzer = GeminiAnalyzer(settings)
    new_items: list[Opportunity] = []

    with get_session() as session:
        try:
            for item in raw_items:
                opportunity = store_new_item(session, item)
                if opportunity is None:
                    continue
                new_items.append(opportunity)
                analysis = analyzer.analyze(item)
                if analysis:
                    _apply_analysis(opportunity, analysis)
            session.commit()
            ranked = rank_recommended(new_items)
        except Exception:
            session.rollback()
            logger.exception("Pipeline database transaction failed")
            raise

    sent = send_digest(settings, ranked) if ranked else False
    return {"fetched": len(raw_items), "new": len(new_items), "recommended": len(ranked), "telegram_sent": sent}

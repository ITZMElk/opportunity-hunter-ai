"""Read-only dashboard queries and template routes."""
from __future__ import annotations

from datetime import datetime, time, timezone

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select

from app.config import PROJECT_ROOT
from app.db import Opportunity, get_session

templates = Jinja2Templates(directory=str(PROJECT_ROOT / "app" / "templates"))
router = APIRouter(include_in_schema=False)


def _statistics() -> dict[str, int | float]:
    today = datetime.combine(datetime.now(timezone.utc).date(), time.min).replace(tzinfo=None)
    with get_session() as session:
        total = session.scalar(select(func.count()).select_from(Opportunity)) or 0
        recommended = session.scalar(select(func.count()).select_from(Opportunity).where(Opportunity.recommended.is_(True))) or 0
        average = session.scalar(select(func.avg(Opportunity.suitability_score))) or 0
        highest = session.scalar(select(func.max(Opportunity.suitability_score))) or 0
        today_new = session.scalar(select(func.count()).select_from(Opportunity).where(Opportunity.created_at >= today)) or 0
        type_counts = dict(session.execute(select(Opportunity.opportunity_type, func.count()).group_by(Opportunity.opportunity_type)).all())
    return {
        "total": total,
        "recommended": recommended,
        "hackathons": type_counts.get("hackathon", 0),
        "internships": type_counts.get("internship", 0),
        "scholarships": type_counts.get("scholarship", 0),
        "cloud_credits": type_counts.get("cloud_credits", 0),
        "average_match": round(float(average), 1),
        "highest_match": round(float(highest), 1),
        "today_new": today_new,
    }


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request) -> HTMLResponse:
    with get_session() as session:
        latest = list(session.scalars(select(Opportunity).order_by(Opportunity.created_at.desc()).limit(6)))
    return templates.TemplateResponse(request, "dashboard.html", {"stats": _statistics(), "opportunities": latest})


@router.get("/opportunities", response_class=HTMLResponse)
def opportunities(
    request: Request,
    q: str = "",
    kind: str = "",
    recommended: bool = False,
    sort: str = Query("newest", pattern="^(newest|score|deadline)$"),
) -> HTMLResponse:
    ordering = {
        "newest": Opportunity.created_at.desc(),
        "score": Opportunity.suitability_score.desc(),
        "deadline": Opportunity.deadline.asc(),
    }[sort]
    statement = select(Opportunity)
    if q:
        statement = statement.where(Opportunity.title.ilike(f"%{q}%") | Opportunity.organizer.ilike(f"%{q}%"))
    if kind:
        statement = statement.where(Opportunity.opportunity_type == kind)
    if recommended:
        statement = statement.where(Opportunity.recommended.is_(True))
    with get_session() as session:
        rows = list(session.scalars(statement.order_by(ordering)))
        types = list(session.scalars(select(Opportunity.opportunity_type).distinct().order_by(Opportunity.opportunity_type)))
    return templates.TemplateResponse(request, "opportunities.html", {"opportunities": rows, "types": [kind for kind in types if kind], "filters": {"q": q, "kind": kind, "recommended": recommended, "sort": sort}})


@router.get("/opportunity/{opportunity_id}", response_class=HTMLResponse)
def opportunity_detail(request: Request, opportunity_id: int) -> HTMLResponse:
    with get_session() as session:
        opportunity = session.get(Opportunity, opportunity_id)
    if opportunity is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return templates.TemplateResponse(request, "detail.html", {"opportunity": opportunity})


@router.get("/stats", response_class=HTMLResponse)
def stats(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "stats.html", {"stats": _statistics()})

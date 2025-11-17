"""API routes for analytics and reporting."""

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.schemas import AnalyticsRequest, AnalyticsResponse
from src.core.logging import get_logger
from src.storage.database.base import get_db
from src.storage.database.models import Case, Document, Hearing, Participant

logger = get_logger(__name__)
router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview", response_model=dict)
async def get_overview(
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get system overview statistics."""
    # Count totals
    cases_count = await db.scalar(select(func.count(Case.id)))
    docs_count = await db.scalar(select(func.count(Document.id)))
    participants_count = await db.scalar(select(func.count(Participant.id)))
    hearings_count = await db.scalar(select(func.count(Hearing.id)))

    # Parsed documents
    parsed_count = await db.scalar(
        select(func.count(Document.id)).where(Document.is_parsed.is_(True))
    )

    return {
        "total_cases": cases_count or 0,
        "total_documents": docs_count or 0,
        "total_participants": participants_count or 0,
        "total_hearings": hearings_count or 0,
        "parsed_documents": parsed_count or 0,
        "parse_rate": round((parsed_count or 0) / (docs_count or 1) * 100, 2),
    }


@router.post("/cases", response_model=AnalyticsResponse)
async def get_case_analytics(
    request: AnalyticsRequest,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get detailed case analytics."""
    query = select(Case)

    # Apply date filters
    if request.date_from:
        query = query.where(Case.filing_date >= request.date_from)
    if request.date_to:
        query = query.where(Case.filing_date <= request.date_to)

    result = await db.execute(query)
    cases = result.scalars().all()

    # Aggregate data
    by_type: dict[str, int] = defaultdict(int)
    by_status: dict[str, int] = defaultdict(int)
    by_court: dict[str, int] = defaultdict(int)
    timeline: dict[str, int] = defaultdict(int)

    for case in cases:
        by_type[case.case_type.value] += 1
        by_status[case.status.value] += 1
        by_court[case.court_name] += 1

        if case.filing_date:
            key = case.filing_date.strftime("%Y-%m")
            timeline[key] += 1

    return AnalyticsResponse(
        total_cases=len(cases),
        by_type=dict(by_type),
        by_status=dict(by_status),
        by_court=dict(by_court),
        timeline=dict(sorted(timeline.items())),
    )


@router.get("/courts", response_model=list[dict])
async def get_court_statistics(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get top courts by case count."""
    query = (
        select(Case.court_name, func.count(Case.id).label("count"))
        .group_by(Case.court_name)
        .order_by(func.count(Case.id).desc())
        .limit(limit)
    )

    result = await db.execute(query)
    courts = result.all()

    return [{"court_name": court, "case_count": count} for court, count in courts]


@router.get("/timeline", response_model=dict)
async def get_timeline(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get case filing timeline."""
    date_from = date.today() - timedelta(days=days)

    query = select(Case).where(Case.filing_date >= date_from)
    result = await db.execute(query)
    cases = result.scalars().all()

    # Group by date
    timeline: dict[str, int] = defaultdict(int)
    for case in cases:
        if case.filing_date:
            key = case.filing_date.isoformat()
            timeline[key] += 1

    return {
        "period": f"{days} days",
        "date_from": date_from.isoformat(),
        "date_to": date.today().isoformat(),
        "data": dict(sorted(timeline.items())),
    }


@router.get("/participants/top", response_model=list[dict])
async def get_top_participants(
    limit: int = Query(10, ge=1, le=50),
    role: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get most active participants."""
    query = (
        select(Participant.name, func.count(Participant.id).label("count"))
        .group_by(Participant.name)
        .order_by(func.count(Participant.id).desc())
        .limit(limit)
    )

    if role:
        query = query.where(Participant.role == role)

    result = await db.execute(query)
    participants = result.all()

    return [{"name": name, "case_count": count} for name, count in participants]

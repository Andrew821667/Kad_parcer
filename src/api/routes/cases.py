"""API routes for cases."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.schemas import (
    CaseCreate,
    CaseDetail,
    CaseInDB,
    CaseSearchParams,
    CaseUpdate,
    PaginatedResponse,
)
from src.core.logging import get_logger
from src.storage.database.base import get_db
from src.storage.database.models import Case, CaseStatus, CaseType
from src.storage.database.repository import CaseRepository

logger = get_logger(__name__)
router = APIRouter(prefix="/cases", tags=["cases"])


@router.post("/", response_model=CaseInDB, status_code=201)
async def create_case(
    case_data: CaseCreate,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Create a new case."""
    repo = CaseRepository(db)

    # Check if case already exists
    existing = await repo.get_by_case_number(case_data.case_number)
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Case {case_data.case_number} already exists",
        )

    case = await repo.create(**case_data.model_dump())
    logger.info("case_created_via_api", case_id=case.id, case_number=case.case_number)
    return case


@router.get("/", response_model=PaginatedResponse)
async def list_cases(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    case_type: CaseType | None = None,
    status: CaseStatus | None = None,
    court_name: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """List cases with pagination and filters."""
    query = select(Case)

    # Apply filters
    if case_type:
        query = query.where(Case.case_type == case_type)
    if status:
        query = query.where(Case.status == status)
    if court_name:
        query = query.where(Case.court_name.ilike(f"%{court_name}%"))

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    result = await db.execute(count_query)
    total = result.scalar_one()

    # Get paginated items
    query = query.order_by(Case.created_at.desc())
    query = query.limit(page_size).offset((page - 1) * page_size)

    result = await db.execute(query)
    cases = result.scalars().all()

    return {
        "items": cases,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/search", response_model=PaginatedResponse)
async def search_cases(
    params: CaseSearchParams = Depends(),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Advanced case search."""
    query = select(Case)

    # Apply search filters
    if params.case_number:
        query = query.where(Case.case_number.ilike(f"%{params.case_number}%"))
    if params.court_name:
        query = query.where(Case.court_name.ilike(f"%{params.court_name}%"))
    if params.judge_name:
        query = query.where(Case.judge_name.ilike(f"%{params.judge_name}%"))
    if params.case_type:
        query = query.where(Case.case_type == params.case_type)
    if params.status:
        query = query.where(Case.status == params.status)
    if params.date_from:
        query = query.where(Case.filing_date >= params.date_from)
    if params.date_to:
        query = query.where(Case.filing_date <= params.date_to)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    result = await db.execute(count_query)
    total = result.scalar_one()

    # Get paginated items
    query = query.order_by(Case.created_at.desc())
    query = query.limit(params.page_size).offset((params.page - 1) * params.page_size)

    result = await db.execute(query)
    cases = result.scalars().all()

    return {
        "items": cases,
        "total": total,
        "page": params.page,
        "page_size": params.page_size,
        "total_pages": (total + params.page_size - 1) // params.page_size,
    }


@router.get("/{case_id}", response_model=CaseDetail)
async def get_case(
    case_id: int,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get case by ID with all related data."""
    repo = CaseRepository(db)
    case = await repo.get_by_id(case_id)

    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    return case


@router.patch("/{case_id}", response_model=CaseInDB)
async def update_case(
    case_id: int,
    case_update: CaseUpdate,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Update case."""
    repo = CaseRepository(db)
    case = await repo.get_by_id(case_id)

    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Update only provided fields
    update_data = case_update.model_dump(exclude_unset=True)
    case = await repo.update(case, **update_data)

    logger.info("case_updated_via_api", case_id=case.id)
    return case


@router.delete("/{case_id}", status_code=204)
async def delete_case(
    case_id: int,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete case."""
    repo = CaseRepository(db)
    case = await repo.get_by_id(case_id)

    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    await db.delete(case)
    await db.commit()

    logger.info("case_deleted_via_api", case_id=case_id)


@router.post("/{case_id}/scrape", response_model=dict)
async def trigger_scrape(
    case_id: int,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Trigger scraping for a case."""
    from src.tasks.scraping_tasks import scrape_case_task

    repo = CaseRepository(db)
    case = await repo.get_by_id(case_id)

    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Trigger Celery task
    task = scrape_case_task.delay(case.case_number)

    return {
        "message": "Scraping task started",
        "task_id": task.id,
        "case_number": case.case_number,
    }


@router.get("/{case_id}/stats", response_model=dict)
async def get_case_stats(
    case_id: int,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get case statistics."""
    repo = CaseRepository(db)
    case = await repo.get_by_id(case_id)

    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    return {
        "case_id": case.id,
        "case_number": case.case_number,
        "participants_count": len(case.participants),
        "documents_count": len(case.documents),
        "hearings_count": len(case.hearings),
        "parsed_documents": sum(1 for d in case.documents if d.is_parsed),
        "last_scraped": case.last_scraped_at.isoformat() if case.last_scraped_at else None,
    }

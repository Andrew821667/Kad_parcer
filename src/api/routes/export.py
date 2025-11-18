"""API routes for data export."""

import csv
import io
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.schemas import ExportRequest
from src.core.logging import get_logger
from src.storage.database.base import get_db
from src.storage.database.models import Case

logger = get_logger(__name__)
router = APIRouter(prefix="/export", tags=["export"])


@router.post("/cases")
async def export_cases(
    request: ExportRequest,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Export cases in various formats."""
    # Build query
    query = select(Case)

    if request.case_ids:
        query = query.where(Case.id.in_(request.case_ids))
    elif request.filters:
        # Apply filters from search params
        filters = request.filters
        if filters.case_number:
            query = query.where(Case.case_number.ilike(f"%{filters.case_number}%"))
        if filters.court_name:
            query = query.where(Case.court_name.ilike(f"%{filters.court_name}%"))
        if filters.case_type:
            query = query.where(Case.case_type == filters.case_type)
        if filters.status:
            query = query.where(Case.status == filters.status)

    # Execute query
    result = await db.execute(query)
    cases = result.scalars().all()

    if not cases:
        raise HTTPException(status_code=404, detail="No cases found for export")

    # Export based on format
    if request.format == "json":
        return _export_json(cases)
    elif request.format == "csv":
        return _export_csv(cases)
    elif request.format == "xlsx":
        return _export_xlsx(cases)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {request.format}")


def _export_json(cases: list[Case]) -> StreamingResponse:
    """Export cases as JSON."""
    data = [
        {
            "id": c.id,
            "case_number": c.case_number,
            "case_type": c.case_type.value,
            "court_name": c.court_name,
            "judge_name": c.judge_name,
            "filing_date": c.filing_date.isoformat() if c.filing_date else None,
            "status": c.status.value,
            "category": c.category,
            "subject": c.subject,
            "created_at": c.created_at.isoformat(),
        }
        for c in cases
    ]

    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    logger.info("cases_exported_json", count=len(cases))

    return StreamingResponse(
        io.BytesIO(json_str.encode("utf-8")),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=cases.json"},
    )


def _export_csv(cases: list[Case]) -> StreamingResponse:
    """Export cases as CSV."""
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow([
        "ID",
        "Case Number",
        "Case Type",
        "Court Name",
        "Judge Name",
        "Filing Date",
        "Status",
        "Category",
        "Created At",
    ])

    # Write data
    for c in cases:
        writer.writerow([
            c.id,
            c.case_number,
            c.case_type.value,
            c.court_name,
            c.judge_name or "",
            c.filing_date.isoformat() if c.filing_date else "",
            c.status.value,
            c.category or "",
            c.created_at.isoformat(),
        ])

    logger.info("cases_exported_csv", count=len(cases))

    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=cases.csv"},
    )


def _export_xlsx(cases: list[Case]) -> StreamingResponse:
    """Export cases as Excel."""
    try:
        from openpyxl import Workbook
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="Excel export requires openpyxl package",
        )

    wb = Workbook()
    ws = wb.active
    ws.title = "Cases"

    # Write header
    headers = [
        "ID",
        "Case Number",
        "Case Type",
        "Court Name",
        "Judge Name",
        "Filing Date",
        "Status",
        "Category",
        "Created At",
    ]
    ws.append(headers)

    # Write data
    for c in cases:
        ws.append([
            c.id,
            c.case_number,
            c.case_type.value,
            c.court_name,
            c.judge_name or "",
            c.filing_date.isoformat() if c.filing_date else "",
            c.status.value,
            c.category or "",
            c.created_at.isoformat(),
        ])

    # Save to bytes
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    logger.info("cases_exported_xlsx", count=len(cases))

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=cases.xlsx"},
    )

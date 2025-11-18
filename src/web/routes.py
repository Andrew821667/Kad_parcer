"""Web UI routes."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="src/web/templates")
router = APIRouter(prefix="/ui", tags=["web-ui"])


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Main dashboard page."""
    return templates.TemplateResponse("index.html", {"request": request})


@router.get("/cases", response_class=HTMLResponse)
async def cases_list(request: Request) -> HTMLResponse:
    """Cases list page."""
    return templates.TemplateResponse("cases.html", {"request": request})


@router.get("/cases/{case_id}", response_class=HTMLResponse)
async def case_detail(request: Request, case_id: int) -> HTMLResponse:
    """Case detail page."""
    return templates.TemplateResponse(
        "case_detail.html",
        {"request": request, "case_id": case_id},
    )


@router.get("/analytics", response_class=HTMLResponse)
async def analytics(request: Request) -> HTMLResponse:
    """Analytics page."""
    return templates.TemplateResponse("analytics.html", {"request": request})


@router.get("/export", response_class=HTMLResponse)
async def export_page(request: Request) -> HTMLResponse:
    """Export page."""
    return templates.TemplateResponse("export.html", {"request": request})

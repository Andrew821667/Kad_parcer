"""FastAPI application."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.api.routes import analytics, auth, cases, documents, export
from src.core.config import get_settings
from src.core.logging import get_logger
from src.web import routes as web_routes

settings = get_settings()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan manager."""
    logger.info("application_starting", version="0.1.0")
    yield
    logger.info("application_shutting_down")


app = FastAPI(
    title="KAD Parser API",
    description="Comprehensive API for parsing court documents from KAD Arbitr",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(auth.router, prefix="/api")
app.include_router(cases.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(export.router, prefix="/api")

# Include Web UI routers
app.include_router(web_routes.router)

# Static files for web UI
try:
    app.mount("/static", StaticFiles(directory="src/web/static"), name="static")
except RuntimeError:
    logger.warning("Static files directory not found, skipping mount")

# Templates for web UI
templates = Jinja2Templates(directory="src/web/templates")


@app.get("/")
async def root() -> dict:
    """Root endpoint."""
    return {
        "name": "KAD Parser API",
        "version": "0.1.0",
        "status": "running",
        "docs": "/api/docs",
        "web_ui": "/ui",
    }


@app.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "0.1.0",
    }


@app.get("/api/info")
async def api_info() -> dict:
    """API information."""
    return {
        "endpoints": {
            "auth": "/api/auth",
            "cases": "/api/cases",
            "documents": "/api/documents",
            "analytics": "/api/analytics",
            "export": "/api/export",
        },
        "features": [
            "JWT authentication and API keys",
            "Full CRUD operations",
            "Advanced search and filtering",
            "Analytics and reporting",
            "Export to JSON/CSV/Excel",
            "Async task processing",
            "File storage (MinIO)",
        ],
    }

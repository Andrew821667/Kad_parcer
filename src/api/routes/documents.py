"""API routes for documents."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.schemas import DocumentCreate, DocumentInDB, DocumentUpdate
from src.core.logging import get_logger
from src.storage.database.base import get_db
from src.storage.database.repository import DocumentRepository
from src.storage.files.minio_storage import get_storage

logger = get_logger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/", response_model=DocumentInDB, status_code=201)
async def create_document(
    document_data: DocumentCreate,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Create a new document."""
    repo = DocumentRepository(db)
    document = await repo.create(**document_data.model_dump())

    logger.info("document_created_via_api", document_id=document.id)
    return document


@router.get("/{document_id}", response_model=DocumentInDB)
async def get_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get document by ID."""
    repo = DocumentRepository(db)
    document = await repo.get_by_id(document_id)

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    return document


@router.patch("/{document_id}", response_model=DocumentInDB)
async def update_document(
    document_id: int,
    document_update: DocumentUpdate,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Update document."""
    repo = DocumentRepository(db)
    document = await repo.get_by_id(document_id)

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    update_data = document_update.model_dump(exclude_unset=True)
    document = await repo.update(document, **update_data)

    logger.info("document_updated_via_api", document_id=document.id)
    return document


@router.post("/{document_id}/upload")
async def upload_document_file(
    document_id: int,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Upload document file to storage."""
    repo = DocumentRepository(db)
    document = await repo.get_by_id(document_id)

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Read file content
    content = await file.read()

    # Upload to MinIO
    storage = get_storage()
    object_name = f"documents/{document_id}/{file.filename}"
    file_path, file_hash = storage.upload_file(content, object_name, file.content_type or "")

    # Update document
    await repo.update(
        document,
        file_path=file_path,
        file_size=len(content),
        file_hash=file_hash,
    )

    logger.info("document_file_uploaded", document_id=document.id, size=len(content))

    return {
        "message": "File uploaded successfully",
        "file_path": file_path,
        "file_size": len(content),
        "file_hash": file_hash,
    }


@router.post("/{document_id}/parse", response_model=dict)
async def parse_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Trigger document parsing task."""
    from src.tasks.scraping_tasks import parse_document_task

    repo = DocumentRepository(db)
    document = await repo.get_by_id(document_id)

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Trigger Celery task
    task = parse_document_task.delay(document_id)

    return {
        "message": "Parsing task started",
        "task_id": task.id,
        "document_id": document_id,
    }


@router.get("/{document_id}/download")
async def download_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get presigned URL for document download."""
    repo = DocumentRepository(db)
    document = await repo.get_by_id(document_id)

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if not document.file_path:
        raise HTTPException(status_code=404, detail="Document file not found")

    # Get presigned URL from MinIO
    storage = get_storage()
    object_name = document.file_path.split("/", 1)[1]  # Remove bucket name
    url = storage.get_file_url(object_name, expires=3600)

    return {
        "url": url,
        "expires_in": 3600,
    }

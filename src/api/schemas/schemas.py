"""Pydantic schemas for API."""

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from src.storage.database.models import (
    CaseStatus,
    CaseType,
    DocumentType,
    ParticipantRole,
    TaskStatus,
)


# Base schemas
class TimestampSchema(BaseModel):
    """Base schema with timestamps."""

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Case schemas
class CaseBase(BaseModel):
    """Base case schema."""

    case_number: str = Field(..., description="Case number")
    case_type: CaseType = Field(..., description="Type of case")
    court_name: str = Field(..., description="Court name")
    judge_name: Optional[str] = Field(None, description="Judge name")
    filing_date: Optional[date] = Field(None, description="Filing date")
    status: CaseStatus = Field(default=CaseStatus.PENDING, description="Case status")
    category: Optional[str] = Field(None, description="Case category")
    subject: Optional[str] = Field(None, description="Case subject")
    kad_url: Optional[str] = Field(None, description="KAD URL")


class CaseCreate(CaseBase):
    """Schema for creating a case."""

    pass


class CaseUpdate(BaseModel):
    """Schema for updating a case."""

    judge_name: Optional[str] = None
    status: Optional[CaseStatus] = None
    category: Optional[str] = None
    subject: Optional[str] = None


class CaseInDB(CaseBase, TimestampSchema):
    """Schema for case in database."""

    id: int
    last_scraped_at: Optional[datetime] = None
    extra_data: Optional[dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


# Participant schemas
class ParticipantBase(BaseModel):
    """Base participant schema."""

    name: str = Field(..., description="Participant name")
    inn: Optional[str] = Field(None, description="INN")
    role: ParticipantRole = Field(..., description="Role in case")
    address: Optional[str] = Field(None, description="Address")


class ParticipantCreate(ParticipantBase):
    """Schema for creating a participant."""

    case_id: int = Field(..., description="Case ID")


class ParticipantInDB(ParticipantBase, TimestampSchema):
    """Schema for participant in database."""

    id: int
    case_id: int
    extra_data: Optional[dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


# Document schemas
class DocumentBase(BaseModel):
    """Base document schema."""

    doc_type: DocumentType = Field(..., description="Document type")
    doc_number: Optional[str] = Field(None, description="Document number")
    doc_date: Optional[date] = Field(None, description="Document date")
    title: Optional[str] = Field(None, description="Document title")
    kad_url: Optional[str] = Field(None, description="KAD URL")


class DocumentCreate(DocumentBase):
    """Schema for creating a document."""

    case_id: int = Field(..., description="Case ID")


class DocumentUpdate(BaseModel):
    """Schema for updating a document."""

    content_text: Optional[str] = None
    is_parsed: Optional[bool] = None
    parse_error: Optional[str] = None


class DocumentInDB(DocumentBase, TimestampSchema):
    """Schema for document in database."""

    id: int
    case_id: int
    content_text: Optional[str] = None
    file_path: Optional[str] = None
    file_url: Optional[str] = None
    file_size: Optional[int] = None
    file_hash: Optional[str] = None
    is_parsed: bool = False
    parse_error: Optional[str] = None
    extra_data: Optional[dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


# Hearing schemas
class HearingBase(BaseModel):
    """Base hearing schema."""

    hearing_date: datetime = Field(..., description="Hearing date")
    hearing_type: Optional[str] = Field(None, description="Hearing type")
    result: Optional[str] = Field(None, description="Hearing result")


class HearingCreate(HearingBase):
    """Schema for creating a hearing."""

    case_id: int = Field(..., description="Case ID")


class HearingInDB(HearingBase, TimestampSchema):
    """Schema for hearing in database."""

    id: int
    case_id: int
    extra_data: Optional[dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


# Task schemas
class TaskBase(BaseModel):
    """Base task schema."""

    task_type: str = Field(..., description="Task type")
    params: Optional[dict[str, Any]] = Field(None, description="Task parameters")


class TaskCreate(TaskBase):
    """Schema for creating a task."""

    pass


class TaskInDB(TaskBase, TimestampSchema):
    """Schema for task in database."""

    id: int
    task_id: str
    status: TaskStatus
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration: Optional[float] = None
    items_processed: int = 0
    items_failed: int = 0

    model_config = ConfigDict(from_attributes=True)


# Response schemas with relationships
class CaseDetail(CaseInDB):
    """Case with related data."""

    participants: list[ParticipantInDB] = []
    documents: list[DocumentInDB] = []
    hearings: list[HearingInDB] = []


# Pagination schemas
class PaginationParams(BaseModel):
    """Pagination parameters."""

    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(50, ge=1, le=100, description="Items per page")


class PaginatedResponse(BaseModel):
    """Paginated response."""

    items: list[Any]
    total: int
    page: int
    page_size: int
    total_pages: int


# Search schemas
class CaseSearchParams(PaginationParams):
    """Case search parameters."""

    case_number: Optional[str] = None
    court_name: Optional[str] = None
    judge_name: Optional[str] = None
    case_type: Optional[CaseType] = None
    status: Optional[CaseStatus] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    participant_name: Optional[str] = None


# Export schemas
class ExportRequest(BaseModel):
    """Export request schema."""

    format: str = Field(..., description="Export format: json, csv, xlsx")
    case_ids: Optional[list[int]] = Field(None, description="Specific case IDs to export")
    filters: Optional[CaseSearchParams] = Field(None, description="Search filters")


# Analytics schemas
class AnalyticsRequest(BaseModel):
    """Analytics request schema."""

    date_from: Optional[date] = None
    date_to: Optional[date] = None
    group_by: str = Field("court", description="Group by: court, case_type, status")


class AnalyticsResponse(BaseModel):
    """Analytics response schema."""

    total_cases: int
    by_type: dict[str, int]
    by_status: dict[str, int]
    by_court: dict[str, int]
    timeline: dict[str, int]

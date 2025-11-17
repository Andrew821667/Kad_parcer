"""SQLAlchemy models for KAD parser."""

import datetime
import enum
from typing import List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.storage.database.base import Base, TimestampMixin


class CaseType(str, enum.Enum):
    """Type of arbitration case."""

    ADMINISTRATIVE = "A"  # Административные дела
    CIVIL = "G"  # Гражданские дела
    BANKRUPTCY = "B"  # Дела о банкротстве


class CaseStatus(str, enum.Enum):
    """Status of case."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ParticipantRole(str, enum.Enum):
    """Role of participant in case."""

    PLAINTIFF = "plaintiff"  # Истец
    DEFENDANT = "defendant"  # Ответчик
    THIRD_PARTY = "third_party"  # Третье лицо
    OTHER = "other"  # Другое


class DocumentType(str, enum.Enum):
    """Type of court document."""

    DECISION = "decision"  # Решение
    RULING = "ruling"  # Определение
    PROTOCOL = "protocol"  # Протокол
    PETITION = "petition"  # Заявление
    COMPLAINT = "complaint"  # Жалоба
    OTHER = "other"  # Другое


class TaskStatus(str, enum.Enum):
    """Status of scraping task."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Case(Base, TimestampMixin):
    """Arbitration case model."""

    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    case_type: Mapped[CaseType] = mapped_column(Enum(CaseType), nullable=False, index=True)
    court_name: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    judge_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    filing_date: Mapped[Optional[datetime.date]] = mapped_column(DateTime, nullable=True)
    status: Mapped[CaseStatus] = mapped_column(
        Enum(CaseStatus), default=CaseStatus.PENDING, nullable=False
    )
    category: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    subject: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Metadata
    kad_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    last_scraped_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)

    # Relationships
    participants: Mapped[List["Participant"]] = relationship(
        "Participant", back_populates="case", cascade="all, delete-orphan"
    )
    documents: Mapped[List["Document"]] = relationship(
        "Document", back_populates="case", cascade="all, delete-orphan"
    )
    hearings: Mapped[List["Hearing"]] = relationship(
        "Hearing", back_populates="case", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_cases_filing_date", "filing_date"),)

    def __repr__(self) -> str:
        return f"<Case(case_number='{self.case_number}', court='{self.court_name}')>"


class Participant(Base, TimestampMixin):
    """Case participant model."""

    __tablename__ = "participants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    inn: Mapped[Optional[str]] = mapped_column(String(12), nullable=True, index=True)
    role: Mapped[ParticipantRole] = mapped_column(Enum(ParticipantRole), nullable=False, index=True)

    # Additional info
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)

    # Relationships
    case: Mapped["Case"] = relationship("Case", back_populates="participants")

    __table_args__ = (
        Index("ix_participants_case_role", "case_id", "role"),
        UniqueConstraint("case_id", "name", "role", name="uq_participant_case"),
    )

    def __repr__(self) -> str:
        return f"<Participant(name='{self.name}', role='{self.role.value}')>"


class Document(Base, TimestampMixin):
    """Court document model."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    doc_type: Mapped[DocumentType] = mapped_column(Enum(DocumentType), nullable=False, index=True)
    doc_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    doc_date: Mapped[Optional[datetime.date]] = mapped_column(DateTime, nullable=True, index=True)

    # Content
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    content_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # File storage
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    file_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    file_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Parsing status
    is_parsed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    parse_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Metadata
    kad_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)

    # Relationships
    case: Mapped["Case"] = relationship("Case", back_populates="documents")

    __table_args__ = (
        Index("ix_documents_case_date", "case_id", "doc_date"),
        Index("ix_documents_case_type", "case_id", "doc_type"),
    )

    def __repr__(self) -> str:
        return f"<Document(type='{self.doc_type.value}', number='{self.doc_number}')>"


class Hearing(Base, TimestampMixin):
    """Court hearing model."""

    __tablename__ = "hearings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    hearing_date: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    hearing_type: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Metadata
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)

    # Relationships
    case: Mapped["Case"] = relationship("Case", back_populates="hearings")

    __table_args__ = (Index("ix_hearings_case_date", "case_id", "hearing_date"),)

    def __repr__(self) -> str:
        return f"<Hearing(date='{self.hearing_date}', type='{self.hearing_type}')>"


class ScrapingTask(Base, TimestampMixin):
    """Scraping task tracking model."""

    __tablename__ = "scraping_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    task_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), default=TaskStatus.PENDING, nullable=False, index=True
    )

    # Task details
    params: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timing
    started_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Statistics
    items_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    items_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    __table_args__ = (
        Index("ix_scraping_tasks_status", "status"),
        Index("ix_scraping_tasks_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ScrapingTask(id='{self.task_id}', status='{self.status.value}')>"

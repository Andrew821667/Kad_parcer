"""Tests for database models."""

import datetime

import pytest

from src.storage.database.models import (
    Case,
    CaseStatus,
    CaseType,
    Document,
    DocumentType,
    Hearing,
    Participant,
    ParticipantRole,
    ScrapingTask,
    TaskStatus,
)


def test_case_model_creation() -> None:
    """Test Case model can be instantiated."""
    case = Case(
        case_number="А40-123456/2024",
        case_type=CaseType.CIVIL,
        court_name="Арбитражный суд города Москвы",
        judge_name="Иванов И.И.",
        status=CaseStatus.PENDING,
    )

    assert case.case_number == "А40-123456/2024"
    assert case.case_type == CaseType.CIVIL
    assert case.court_name == "Арбитражный суд города Москвы"
    assert case.judge_name == "Иванов И.И."
    assert case.status == CaseStatus.PENDING


def test_case_repr() -> None:
    """Test Case string representation."""
    case = Case(
        case_number="А40-123456/2024",
        case_type=CaseType.CIVIL,
        court_name="Арбитражный суд города Москвы",
    )

    assert "А40-123456/2024" in repr(case)
    assert "Арбитражный суд города Москвы" in repr(case)


def test_participant_model_creation() -> None:
    """Test Participant model can be instantiated."""
    participant = Participant(
        case_id=1,
        name="ООО Тестовая Компания",
        inn="1234567890",
        role=ParticipantRole.PLAINTIFF,
    )

    assert participant.name == "ООО Тестовая Компания"
    assert participant.inn == "1234567890"
    assert participant.role == ParticipantRole.PLAINTIFF


def test_document_model_creation() -> None:
    """Test Document model can be instantiated."""
    document = Document(
        case_id=1,
        doc_type=DocumentType.DECISION,
        doc_number="123",
        doc_date=datetime.date(2024, 1, 15),
        title="Решение суда",
        is_parsed=False,
    )

    assert document.doc_type == DocumentType.DECISION
    assert document.doc_number == "123"
    assert document.title == "Решение суда"
    assert document.is_parsed is False


def test_hearing_model_creation() -> None:
    """Test Hearing model can be instantiated."""
    hearing = Hearing(
        case_id=1,
        hearing_date=datetime.datetime(2024, 2, 15, 10, 0),
        hearing_type="Предварительное заседание",
        result="Заседание отложено",
    )

    assert hearing.hearing_type == "Предварительное заседание"
    assert hearing.result == "Заседание отложено"


def test_scraping_task_model_creation() -> None:
    """Test ScrapingTask model can be instantiated."""
    task = ScrapingTask(
        task_id="test-task-123",
        task_type="scrape_case",
        status=TaskStatus.PENDING,
        params={"case_number": "А40-123456/2024"},
        items_processed=0,
        items_failed=0,
    )

    assert task.task_id == "test-task-123"
    assert task.task_type == "scrape_case"
    assert task.status == TaskStatus.PENDING
    assert task.items_processed == 0


def test_case_type_enum() -> None:
    """Test CaseType enum values."""
    assert CaseType.ADMINISTRATIVE.value == "A"
    assert CaseType.CIVIL.value == "G"
    assert CaseType.BANKRUPTCY.value == "B"


def test_participant_role_enum() -> None:
    """Test ParticipantRole enum values."""
    assert ParticipantRole.PLAINTIFF.value == "plaintiff"
    assert ParticipantRole.DEFENDANT.value == "defendant"
    assert ParticipantRole.THIRD_PARTY.value == "third_party"


def test_document_type_enum() -> None:
    """Test DocumentType enum values."""
    assert DocumentType.DECISION.value == "decision"
    assert DocumentType.RULING.value == "ruling"
    assert DocumentType.PROTOCOL.value == "protocol"


def test_task_status_enum() -> None:
    """Test TaskStatus enum values."""
    assert TaskStatus.PENDING.value == "pending"
    assert TaskStatus.RUNNING.value == "running"
    assert TaskStatus.SUCCESS.value == "success"
    assert TaskStatus.FAILED.value == "failed"

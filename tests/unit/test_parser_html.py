"""Tests for HTML parser."""

import pytest

from src.parser.html_parser import HTMLCaseParser
from src.storage.database.models import CaseType, DocumentType, ParticipantRole


def test_html_parser_initialization() -> None:
    """Test HTML parser initialization."""
    html = "<html><body>Test</body></html>"
    parser = HTMLCaseParser(html)

    assert parser.html == html
    assert parser.soup is not None


def test_parse_case_info_empty() -> None:
    """Test parsing empty case info."""
    html = "<html><body></body></html>"
    parser = HTMLCaseParser(html)

    result = parser.parse_case_info()
    assert isinstance(result, dict)


def test_extract_case_type_administrative() -> None:
    """Test extracting administrative case type."""
    html = "<html></html>"
    parser = HTMLCaseParser(html)

    case_type = parser._extract_case_type("А40-123456/2024")
    assert case_type == CaseType.ADMINISTRATIVE.value


def test_extract_case_type_bankruptcy() -> None:
    """Test extracting bankruptcy case type."""
    html = "<html></html>"
    parser = HTMLCaseParser(html)

    case_type = parser._extract_case_type("Б12-34567/2024")
    assert case_type == CaseType.BANKRUPTCY.value


def test_map_participant_role_plaintiff() -> None:
    """Test mapping plaintiff role."""
    html = "<html></html>"
    parser = HTMLCaseParser(html)

    role = parser._map_participant_role("Истец")
    assert role == ParticipantRole.PLAINTIFF.value

    role = parser._map_participant_role("Заявитель")
    assert role == ParticipantRole.PLAINTIFF.value


def test_map_participant_role_defendant() -> None:
    """Test mapping defendant role."""
    html = "<html></html>"
    parser = HTMLCaseParser(html)

    role = parser._map_participant_role("Ответчик")
    assert role == ParticipantRole.DEFENDANT.value


def test_map_participant_role_third_party() -> None:
    """Test mapping third party role."""
    html = "<html></html>"
    parser = HTMLCaseParser(html)

    role = parser._map_participant_role("Третье лицо")
    assert role == ParticipantRole.THIRD_PARTY.value

    role = parser._map_participant_role("3-е лицо")
    assert role == ParticipantRole.THIRD_PARTY.value


def test_map_document_type_decision() -> None:
    """Test mapping decision document type."""
    html = "<html></html>"
    parser = HTMLCaseParser(html)

    doc_type = parser._map_document_type("Решение")
    assert doc_type == DocumentType.DECISION.value


def test_map_document_type_ruling() -> None:
    """Test mapping ruling document type."""
    html = "<html></html>"
    parser = HTMLCaseParser(html)

    doc_type = parser._map_document_type("Определение")
    assert doc_type == DocumentType.RULING.value


def test_parse_date_formats() -> None:
    """Test parsing various date formats."""
    html = "<html></html>"
    parser = HTMLCaseParser(html)

    # DD.MM.YYYY format
    date = parser._parse_date("15.01.2024")
    assert date == "2024-01-15"

    # YYYY-MM-DD format
    date = parser._parse_date("2024-01-15")
    assert date == "2024-01-15"

    # DD/MM/YYYY format
    date = parser._parse_date("15/01/2024")
    assert date == "2024-01-15"


def test_parse_date_invalid() -> None:
    """Test parsing invalid date."""
    html = "<html></html>"
    parser = HTMLCaseParser(html)

    date = parser._parse_date("invalid")
    assert date is None


def test_parse_datetime_formats() -> None:
    """Test parsing datetime formats."""
    html = "<html></html>"
    parser = HTMLCaseParser(html)

    # DD.MM.YYYY HH:MM format
    dt = parser._parse_datetime("15.01.2024 14:30")
    assert dt == "2024-01-15T14:30:00"


def test_parse_participants_empty() -> None:
    """Test parsing participants from empty HTML."""
    html = "<html><body></body></html>"
    parser = HTMLCaseParser(html)

    participants = parser.parse_participants()
    assert participants == []


def test_parse_documents_empty() -> None:
    """Test parsing documents from empty HTML."""
    html = "<html><body></body></html>"
    parser = HTMLCaseParser(html)

    documents = parser.parse_documents()
    assert documents == []


def test_parse_hearings_empty() -> None:
    """Test parsing hearings from empty HTML."""
    html = "<html><body></body></html>"
    parser = HTMLCaseParser(html)

    hearings = parser.parse_hearings()
    assert hearings == []

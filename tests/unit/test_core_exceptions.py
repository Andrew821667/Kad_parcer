"""Tests for core exceptions module."""

import pytest

from src.core.exceptions import (
    APIException,
    BadRequestException,
    CaptchaException,
    ConfigurationException,
    ConnectionException,
    DatabaseException,
    DOCXParseException,
    FileStorageException,
    HTMLParseException,
    KadParserException,
    NotFoundException,
    ParserException,
    PDFParseException,
    RateLimitException,
    ScraperException,
    StorageException,
    TaskException,
    UnauthorizedException,
    ValidationException,
)


def test_base_exception() -> None:
    """Test base KadParserException."""
    exc = KadParserException("Test error", details={"key": "value"})

    assert str(exc) == "Test error"
    assert exc.message == "Test error"
    assert exc.details == {"key": "value"}


def test_base_exception_no_details() -> None:
    """Test base exception without details."""
    exc = KadParserException("Test error")

    assert exc.details == {}


def test_scraper_exceptions() -> None:
    """Test scraper exception hierarchy."""
    exc = ScraperException("Scraper error")
    assert isinstance(exc, KadParserException)

    rate_limit_exc = RateLimitException("Rate limited")
    assert isinstance(rate_limit_exc, ScraperException)

    captcha_exc = CaptchaException("Captcha found")
    assert isinstance(captcha_exc, ScraperException)

    conn_exc = ConnectionException("Connection failed")
    assert isinstance(conn_exc, ScraperException)


def test_parser_exceptions() -> None:
    """Test parser exception hierarchy."""
    exc = ParserException("Parse error")
    assert isinstance(exc, KadParserException)

    html_exc = HTMLParseException("HTML parse error")
    assert isinstance(html_exc, ParserException)

    pdf_exc = PDFParseException("PDF parse error")
    assert isinstance(pdf_exc, ParserException)

    docx_exc = DOCXParseException("DOCX parse error")
    assert isinstance(docx_exc, ParserException)


def test_storage_exceptions() -> None:
    """Test storage exception hierarchy."""
    exc = StorageException("Storage error")
    assert isinstance(exc, KadParserException)

    db_exc = DatabaseException("DB error")
    assert isinstance(db_exc, StorageException)

    file_exc = FileStorageException("File error")
    assert isinstance(file_exc, StorageException)


def test_api_exception_with_status() -> None:
    """Test API exception with status code."""
    exc = APIException("API error", status_code=500, details={"error": "internal"})

    assert exc.message == "API error"
    assert exc.status_code == 500
    assert exc.details == {"error": "internal"}


def test_not_found_exception() -> None:
    """Test NotFoundException defaults."""
    exc = NotFoundException()

    assert exc.status_code == 404
    assert exc.message == "Resource not found"


def test_bad_request_exception() -> None:
    """Test BadRequestException defaults."""
    exc = BadRequestException()

    assert exc.status_code == 400
    assert exc.message == "Bad request"


def test_unauthorized_exception() -> None:
    """Test UnauthorizedException defaults."""
    exc = UnauthorizedException()

    assert exc.status_code == 401
    assert exc.message == "Unauthorized"

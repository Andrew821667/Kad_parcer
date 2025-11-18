"""Custom exceptions for the KAD parser application."""


class KadParserException(Exception):
    """Base exception for all KAD parser errors."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        """Initialize exception with message and optional details.

        Args:
            message: Error message
            details: Additional error details
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ScraperException(KadParserException):
    """Exceptions related to web scraping operations."""

    pass


class RateLimitException(ScraperException):
    """Rate limit exceeded."""

    pass


class CaptchaException(ScraperException):
    """Captcha encountered and cannot be bypassed."""

    pass


class ConnectionException(ScraperException):
    """Connection to KAD server failed."""

    pass


class ParserException(KadParserException):
    """Exceptions related to parsing operations."""

    pass


class HTMLParseException(ParserException):
    """Failed to parse HTML content."""

    pass


class PDFParseException(ParserException):
    """Failed to parse PDF document."""

    pass


class DOCXParseException(ParserException):
    """Failed to parse DOCX document."""

    pass


class StorageException(KadParserException):
    """Exceptions related to storage operations."""

    pass


class DatabaseException(StorageException):
    """Database operation failed."""

    pass


class FileStorageException(StorageException):
    """File storage operation failed."""

    pass


class ValidationException(KadParserException):
    """Data validation failed."""

    pass


class ConfigurationException(KadParserException):
    """Configuration error."""

    pass


class TaskException(KadParserException):
    """Celery task execution error."""

    pass


class APIException(KadParserException):
    """API-related exceptions."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        details: dict | None = None,
    ) -> None:
        """Initialize API exception.

        Args:
            message: Error message
            status_code: HTTP status code
            details: Additional error details
        """
        super().__init__(message, details)
        self.status_code = status_code


class NotFoundException(APIException):
    """Resource not found."""

    def __init__(self, message: str = "Resource not found", details: dict | None = None) -> None:
        """Initialize with 404 status code."""
        super().__init__(message, status_code=404, details=details)


class BadRequestException(APIException):
    """Bad request."""

    def __init__(self, message: str = "Bad request", details: dict | None = None) -> None:
        """Initialize with 400 status code."""
        super().__init__(message, status_code=400, details=details)


class UnauthorizedException(APIException):
    """Unauthorized access."""

    def __init__(self, message: str = "Unauthorized", details: dict | None = None) -> None:
        """Initialize with 401 status code."""
        super().__init__(message, status_code=401, details=details)

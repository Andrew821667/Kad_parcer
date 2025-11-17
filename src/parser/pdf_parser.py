"""PDF parser for court documents."""

import io
from typing import Any, Optional

import pdfplumber
from pypdf2 import PdfReader

from src.core.exceptions import PDFParseException
from src.core.logging import get_logger

logger = get_logger(__name__)


class PDFDocumentParser:
    """Parser for PDF court documents."""

    def __init__(self, pdf_content: bytes) -> None:
        """Initialize parser with PDF content.

        Args:
            pdf_content: PDF file content as bytes
        """
        self.pdf_content = pdf_content
        self.pdf_file = io.BytesIO(pdf_content)

    def extract_text(self, method: str = "pdfplumber") -> str:
        """Extract text from PDF.

        Args:
            method: Extraction method ('pdfplumber' or 'pypdf2')

        Returns:
            Extracted text

        Raises:
            PDFParseException: If extraction fails
        """
        try:
            if method == "pdfplumber":
                return self._extract_with_pdfplumber()
            elif method == "pypdf2":
                return self._extract_with_pypdf2()
            else:
                raise ValueError(f"Unknown extraction method: {method}")

        except Exception as e:
            logger.error("pdf_text_extraction_failed", error=str(e), method=method)
            raise PDFParseException(f"Failed to extract text from PDF: {e}") from e

    def _extract_with_pdfplumber(self) -> str:
        """Extract text using pdfplumber.

        Returns:
            Extracted text
        """
        text_parts = []

        with pdfplumber.open(self.pdf_file) as pdf:
            logger.debug("extracting_pdf_text", pages=len(pdf.pages), method="pdfplumber")

            for page_num, page in enumerate(pdf.pages, 1):
                try:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
                except Exception as e:
                    logger.warning(
                        "page_extraction_failed",
                        page=page_num,
                        error=str(e),
                    )

        full_text = "\n\n".join(text_parts)
        logger.debug("pdf_text_extracted", length=len(full_text), pages=len(text_parts))

        return full_text

    def _extract_with_pypdf2(self) -> str:
        """Extract text using PyPDF2.

        Returns:
            Extracted text
        """
        text_parts = []
        self.pdf_file.seek(0)

        reader = PdfReader(self.pdf_file)
        logger.debug("extracting_pdf_text", pages=len(reader.pages), method="pypdf2")

        for page_num, page in enumerate(reader.pages, 1):
            try:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            except Exception as e:
                logger.warning(
                    "page_extraction_failed",
                    page=page_num,
                    error=str(e),
                )

        full_text = "\n\n".join(text_parts)
        logger.debug("pdf_text_extracted", length=len(full_text), pages=len(text_parts))

        return full_text

    def get_metadata(self) -> dict[str, Any]:
        """Extract PDF metadata.

        Returns:
            Dictionary with metadata

        Raises:
            PDFParseException: If extraction fails
        """
        try:
            self.pdf_file.seek(0)
            reader = PdfReader(self.pdf_file)

            metadata: dict[str, Any] = {
                "page_count": len(reader.pages),
            }

            # Extract document info
            if reader.metadata:
                info = reader.metadata
                metadata.update(
                    {
                        "title": info.get("/Title"),
                        "author": info.get("/Author"),
                        "subject": info.get("/Subject"),
                        "creator": info.get("/Creator"),
                        "producer": info.get("/Producer"),
                        "creation_date": info.get("/CreationDate"),
                        "modification_date": info.get("/ModDate"),
                    }
                )

            logger.debug("pdf_metadata_extracted", metadata=metadata)
            return metadata

        except Exception as e:
            logger.error("pdf_metadata_extraction_failed", error=str(e))
            raise PDFParseException(f"Failed to extract PDF metadata: {e}") from e

    def extract_with_fallback(self) -> str:
        """Extract text with fallback to alternative method.

        Returns:
            Extracted text

        Raises:
            PDFParseException: If all methods fail
        """
        # Try pdfplumber first (better quality)
        try:
            text = self._extract_with_pdfplumber()
            if text and len(text.strip()) > 0:
                return text
        except Exception as e:
            logger.warning("pdfplumber_failed", error=str(e))

        # Fallback to PyPDF2
        try:
            self.pdf_file.seek(0)
            text = self._extract_with_pypdf2()
            if text and len(text.strip()) > 0:
                return text
        except Exception as e:
            logger.warning("pypdf2_failed", error=str(e))

        raise PDFParseException("All PDF extraction methods failed")

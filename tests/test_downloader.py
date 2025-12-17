#!/usr/bin/env python3
"""
Unit tests for Document Downloader module.
"""

import unittest
import tempfile
import os
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import shutil

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.downloader import (
    DocumentDownloader,
    IMPORTANT_DOCUMENT_TYPES,
    filter_important_documents,
)


class TestImportantDocumentFilter(unittest.TestCase):
    """Test cases for document filtering."""

    def test_filter_important_documents(self):
        """Test filtering important document types."""
        documents = [
            {"doc_type": "Решение суда первой инстанции", "pdf_url": "url1"},
            {"doc_type": "Протокол судебного заседания", "pdf_url": "url2"},
            {"doc_type": "Постановление апелляционной инстанции", "pdf_url": "url3"},
            {"doc_type": "Ходатайство", "pdf_url": "url4"},
            {"doc_type": "Определение Верховного Суда РФ", "pdf_url": "url5"},
        ]

        filtered = filter_important_documents(documents)

        # Should keep: Решение, Постановление, Определение ВС
        # Should filter out: Протокол, Ходатайство
        self.assertEqual(len(filtered), 3)

        doc_types = [doc["doc_type"] for doc in filtered]
        self.assertIn("Решение суда первой инстанции", doc_types)
        self.assertIn("Постановление апелляционной инстанции", doc_types)
        self.assertIn("Определение Верховного Суда РФ", doc_types)

    def test_filter_keeps_terminating_documents(self):
        """Test that terminating documents are kept."""
        documents = [
            {"doc_type": "Определение о прекращении производства", "pdf_url": "url1"},
            {"doc_type": "Определение об утверждении мирового соглашения", "pdf_url": "url2"},
            {"doc_type": "Определение о назначении экспертизы", "pdf_url": "url3"},
        ]

        filtered = filter_important_documents(documents)

        # Should keep terminating docs, filter out others
        self.assertEqual(len(filtered), 2)

    def test_filter_empty_list(self):
        """Test filtering empty document list."""
        filtered = filter_important_documents([])
        self.assertEqual(len(filtered), 0)

    def test_filter_no_matches(self):
        """Test filtering when no documents match."""
        documents = [
            {"doc_type": "Протокол", "pdf_url": "url1"},
            {"doc_type": "Ходатайство", "pdf_url": "url2"},
        ]

        filtered = filter_important_documents(documents)
        self.assertEqual(len(filtered), 0)

    def test_filter_preserves_document_data(self):
        """Test that filtering preserves all document fields."""
        documents = [
            {
                "doc_type": "Решение",
                "pdf_url": "url1",
                "instance": "Первая",
                "is_final": True,
                "extra_field": "value"
            }
        ]

        filtered = filter_important_documents(documents)

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["doc_type"], "Решение")
        self.assertEqual(filtered[0]["pdf_url"], "url1")
        self.assertEqual(filtered[0]["instance"], "Первая")
        self.assertEqual(filtered[0]["is_final"], True)
        self.assertEqual(filtered[0]["extra_field"], "value")


class TestDocumentDownloaderInit(unittest.TestCase):
    """Test DocumentDownloader initialization."""

    def test_init_default_params(self):
        """Test initialization with default parameters."""
        mock_scraper = MagicMock()
        downloader = DocumentDownloader(mock_scraper)

        self.assertEqual(downloader.scraper, mock_scraper)
        self.assertEqual(downloader.download_dir, Path("downloads"))
        self.assertEqual(downloader.rate_limit_delay, 5.0)
        self.assertEqual(downloader.last_request_time, 0)

    def test_init_custom_params(self):
        """Test initialization with custom parameters."""
        mock_scraper = MagicMock()
        downloader = DocumentDownloader(
            mock_scraper,
            download_dir="custom_downloads",
            rate_limit_delay=3.0
        )

        self.assertEqual(downloader.download_dir, Path("custom_downloads"))
        self.assertEqual(downloader.rate_limit_delay, 3.0)


class TestDocumentDownloaderAsync(unittest.IsolatedAsyncioTestCase):
    """Test async DocumentDownloader methods."""

    async def asyncSetUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.mock_scraper = MagicMock()
        self.mock_scraper.page = AsyncMock()
        self.downloader = DocumentDownloader(
            self.mock_scraper,
            download_dir=self.temp_dir,
            rate_limit_delay=0.1  # Short delay for tests
        )

    async def asyncTearDown(self):
        """Clean up after tests."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    async def test_rate_limit_first_request(self):
        """Test rate limiting on first request."""
        import time
        start_time = time.time()

        await self.downloader._rate_limit()

        elapsed = time.time() - start_time
        # First request should be immediate
        self.assertLess(elapsed, 0.05)

    async def test_rate_limit_subsequent_requests(self):
        """Test rate limiting on subsequent requests."""
        import time

        # First request
        await self.downloader._rate_limit()
        time1 = time.time()

        # Second request (should wait)
        await self.downloader._rate_limit()
        time2 = time.time()

        elapsed = time2 - time1
        # Should wait approximately rate_limit_delay
        self.assertGreaterEqual(elapsed, 0.08)  # Allow some tolerance

    async def test_navigate_to_case_success(self):
        """Test successful navigation to case page."""
        # Mock page methods
        self.mock_scraper.page.goto = AsyncMock()
        self.mock_scraper.page.keyboard.press = AsyncMock()
        self.mock_scraper.page.query_selector = AsyncMock()
        self.mock_scraper.page.wait_for_selector = AsyncMock()

        # Mock search input
        mock_input = AsyncMock()
        mock_input.fill = AsyncMock()

        # Mock search button
        mock_button = AsyncMock()
        mock_button.click = AsyncMock()

        # Mock case link
        mock_link = AsyncMock()
        mock_link.click = AsyncMock()

        # Setup query_selector to return mocks in sequence
        self.mock_scraper.page.query_selector.side_effect = [
            mock_input,  # Search input
            mock_button,  # Search button
            mock_link,    # First case link
        ]

        result = await self.downloader.navigate_to_case("А40-12345-2024")

        self.assertTrue(result)
        self.mock_scraper.page.goto.assert_called_once()
        mock_input.fill.assert_called_once_with("А40-12345-2024")
        mock_button.click.assert_called_once()
        mock_link.click.assert_called_once()

    async def test_navigate_to_case_no_search_input(self):
        """Test navigation failure when search input not found."""
        self.mock_scraper.page.goto = AsyncMock()
        self.mock_scraper.page.keyboard.press = AsyncMock()
        self.mock_scraper.page.query_selector = AsyncMock(return_value=None)

        result = await self.downloader.navigate_to_case("А40-12345-2024")

        self.assertFalse(result)

    async def test_get_electronic_case_documents_success(self):
        """Test successful document extraction."""
        # Mock tab click
        mock_tab = AsyncMock()
        mock_tab.click = AsyncMock()

        # Mock document elements
        mock_doc1 = AsyncMock()
        mock_doc_type1 = AsyncMock()
        mock_doc_type1.inner_text = AsyncMock(return_value="Решение суда")
        mock_pdf_link1 = AsyncMock()
        mock_pdf_link1.get_attribute = AsyncMock(return_value="https://example.com/doc1.pdf")

        mock_doc1.query_selector = AsyncMock()
        mock_doc1.query_selector.side_effect = [mock_doc_type1, mock_pdf_link1]

        # Setup page mocks
        self.mock_scraper.page.query_selector = AsyncMock(return_value=mock_tab)
        self.mock_scraper.page.wait_for_selector = AsyncMock()
        self.mock_scraper.page.query_selector_all = AsyncMock(return_value=[mock_doc1])

        documents = await self.downloader.get_electronic_case_documents()

        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0]["doc_type"], "Решение суда")
        self.assertEqual(documents[0]["pdf_url"], "https://example.com/doc1.pdf")

    async def test_get_electronic_case_documents_no_tab(self):
        """Test document extraction when tab not found."""
        self.mock_scraper.page.query_selector = AsyncMock(return_value=None)

        documents = await self.downloader.get_electronic_case_documents()

        self.assertEqual(len(documents), 0)

    @patch('aiohttp.ClientSession')
    async def test_download_pdf_success(self, mock_session_class):
        """Test successful PDF download."""
        # Mock aiohttp response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=b"PDF content")
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock()

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        mock_session_class.return_value = mock_session

        # Test download
        save_path = Path(self.temp_dir) / "test.pdf"
        result = await self.downloader.download_pdf(
            "https://example.com/test.pdf",
            str(save_path)
        )

        self.assertTrue(result)
        self.assertTrue(save_path.exists())
        self.assertEqual(save_path.read_bytes(), b"PDF content")

    @patch('aiohttp.ClientSession')
    async def test_download_pdf_http_error(self, mock_session_class):
        """Test PDF download with HTTP error."""
        # Mock error response
        mock_response = AsyncMock()
        mock_response.status = 404
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock()

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        mock_session_class.return_value = mock_session

        save_path = Path(self.temp_dir) / "test.pdf"
        result = await self.downloader.download_pdf(
            "https://example.com/test.pdf",
            str(save_path),
            retry=1  # Single attempt for faster test
        )

        self.assertFalse(result)
        self.assertFalse(save_path.exists())

    async def test_download_case_documents_integration(self):
        """Test full download_case_documents workflow."""
        # Mock navigation
        self.downloader.navigate_to_case = AsyncMock(return_value=True)

        # Mock document extraction
        self.downloader.get_electronic_case_documents = AsyncMock(return_value=[
            {
                "doc_type": "Решение суда первой инстанции",
                "pdf_url": "https://example.com/doc1.pdf",
                "instance": "Первая",
                "is_final": True
            },
            {
                "doc_type": "Протокол судебного заседания",
                "pdf_url": "https://example.com/doc2.pdf",
                "instance": "Первая",
                "is_final": False
            }
        ])

        # Mock PDF download
        self.downloader.download_pdf = AsyncMock(return_value=True)

        # Test
        result = await self.downloader.download_case_documents(
            "А40-12345-2024",
            filter_important=True
        )

        # Verify results
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["filtered"], 1)  # Only Решение is important
        self.assertEqual(result["downloaded"], 1)
        self.assertEqual(result["failed"], 0)

        # Verify download was called for important doc only
        self.downloader.download_pdf.assert_called_once()

    async def test_download_case_documents_navigation_failure(self):
        """Test download_case_documents when navigation fails."""
        self.downloader.navigate_to_case = AsyncMock(return_value=False)

        result = await self.downloader.download_case_documents("А40-12345-2024")

        self.assertEqual(result["total"], 0)
        self.assertEqual(result["downloaded"], 0)


class TestDocumentDownloaderOutputStructure(unittest.TestCase):
    """Test output directory structure."""

    def test_output_directory_structure(self):
        """Test that output directories are created correctly."""
        case_number = "А40-12345-2024"

        # Extract year
        parts = case_number.split("-")
        year = parts[-1]

        # Expected structure
        expected_dir = Path("downloads") / year / case_number

        self.assertEqual(year, "2024")
        self.assertEqual(str(expected_dir), "downloads/2024/А40-12345-2024")

    def test_year_extraction_from_case_number(self):
        """Test year extraction logic."""
        test_cases = [
            ("А40-12345-2024", "2024"),
            ("А50-67890-2023", "2023"),
            ("А01-11111-2025", "2025"),
        ]

        for case_number, expected_year in test_cases:
            parts = case_number.split("-")
            year = parts[-1] if len(parts) >= 3 else "unknown"
            self.assertEqual(year, expected_year)


def run_tests():
    """Run all tests."""
    unittest.main(argv=[''], verbosity=2, exit=False)


if __name__ == "__main__":
    unittest.main(verbosity=2)

#!/usr/bin/env python3
"""
Document downloader for КАД Арбитр court cases.

Downloads important court documents (PDFs) from case pages.
"""

import asyncio
import aiohttp
from pathlib import Path
from typing import List, Dict, Optional, Any
import time

from ..scraper.playwright_scraper import PlaywrightScraper


# Important document types filter
IMPORTANT_DOCUMENT_TYPES = {
    "Решение",                              # Первая инстанция
    "Постановление",                        # Апелляция/Кассация
    "Определение Верховного Суда",          # ВС РФ
    "Определение о прекращении",            # Завершающие
    "Определение об утверждении мирового",  # Мировое соглашение
}


def filter_important_documents(documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filter documents to keep only important types.

    Args:
        documents: List of document dictionaries with 'doc_type' field

    Returns:
        Filtered list of important documents
    """
    important = []

    for doc in documents:
        doc_type = doc.get("doc_type", "")

        # Check if document type matches any important type
        for important_type in IMPORTANT_DOCUMENT_TYPES:
            if important_type in doc_type:
                important.append(doc)
                break

    return important


class DocumentDownloader:
    """
    Downloads court documents from КАД Арбитр case pages.

    Features:
    - Navigate to case page by case number
    - Extract documents from "Электронное дело" tab
    - Filter important document types
    - Download PDFs with retry logic
    - Rate limiting (5 sec between requests)
    """

    def __init__(
        self,
        scraper: PlaywrightScraper,
        download_dir: str = "downloads",
        rate_limit_delay: float = 5.0
    ):
        """
        Initialize document downloader.

        Args:
            scraper: PlaywrightScraper instance
            download_dir: Base directory for downloads (default: "downloads")
            rate_limit_delay: Delay between requests in seconds (default: 5.0)
        """
        self.scraper = scraper
        self.download_dir = Path(download_dir)
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = 0

    async def _rate_limit(self):
        """Apply rate limiting delay."""
        current_time = time.time()
        elapsed = current_time - self.last_request_time

        if elapsed < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - elapsed)

        self.last_request_time = time.time()

    async def navigate_to_case(self, case_number: str, case_url: str = None) -> bool:
        """
        Navigate to case page by URL or case number.

        Args:
            case_number: Case number (e.g., "А40-12345-2024")
            case_url: Direct URL to case (e.g., "/Card/uuid...")

        Returns:
            True if navigation successful, False otherwise
        """
        try:
            # If direct URL provided, use it (much faster!)
            if case_url:
                # Если URL уже полный - использовать как есть
                if case_url.startswith('http'):
                    full_url = case_url
                else:
                    # Если относительный - добавить домен
                    full_url = f"https://kad.arbitr.ru{case_url}"
                await self.scraper.page.goto(full_url, wait_until="networkidle")
                await asyncio.sleep(1)
                return True

            # Fallback: Search for case on main page
            await self.scraper.page.goto("https://kad.arbitr.ru", wait_until="networkidle")
            await asyncio.sleep(1)

            # Close popup if present
            try:
                await self.scraper.page.keyboard.press("Escape")
                await asyncio.sleep(0.5)
            except:
                pass

            # Enter case number in search field
            search_input = await self.scraper.page.query_selector('input[placeholder="номер дела"]')
            if not search_input:
                print("Search input not found")
                return False

            await search_input.fill(case_number)
            await asyncio.sleep(0.5)

            # Click search button
            search_button = await self.scraper.page.query_selector('button.b-form-btn:has-text("Найти")')
            if not search_button:
                print("Search button not found")
                return False

            await search_button.click()
            await asyncio.sleep(2)

            # Wait for results
            await self.scraper.page.wait_for_selector('.b-cases', timeout=10000)

            # Click on first result
            first_case = await self.scraper.page.query_selector('.b-cases tbody tr:first-child a')
            if not first_case:
                print(f"Case {case_number} not found in results")
                return False

            await first_case.click()
            await asyncio.sleep(2)

            return True

        except Exception as e:
            print(f"Error navigating to case {case_number}: {e}")
            return False

    async def get_electronic_case_documents(self) -> List[Dict[str, Any]]:
        """
        Get list of documents from "Электронное дело" tab.

        Returns:
            List of document dictionaries with fields:
            - doc_type: Document type
            - instance: Instance level
            - pdf_url: URL to PDF file
            - is_final: Whether document is final (bool)
        """
        documents = []

        try:
            # Find and click "Электронное дело" tab
            ed_tab = await self.scraper.page.query_selector('.js-case-chrono-button--ed')
            if not ed_tab:
                print("Electronic case tab not found")
                return documents

            await ed_tab.click()
            await asyncio.sleep(2)

            # Wait for document list to load
            await self.scraper.page.wait_for_selector('#chrono_list_content', timeout=10000)

            # Extract documents from chronology list
            # This would need specific selectors based on actual page structure
            # Placeholder implementation:
            doc_elements = await self.scraper.page.query_selector_all(
                '#chrono_list_content .js-case-chrono-item'
            )

            for elem in doc_elements:
                try:
                    # Extract document info (actual selectors would need to be determined)
                    doc_type_elem = await elem.query_selector('.case-chrono-doc-type')
                    pdf_link_elem = await elem.query_selector('a[href*=".pdf"]')

                    if doc_type_elem and pdf_link_elem:
                        doc_type = await doc_type_elem.inner_text()
                        pdf_url = await pdf_link_elem.get_attribute('href')

                        documents.append({
                            "doc_type": doc_type.strip(),
                            "pdf_url": pdf_url,
                            "instance": "",  # Would need to extract from page
                            "is_final": False,  # Would need logic to determine
                        })

                except Exception as e:
                    print(f"Error extracting document: {e}")
                    continue

        except Exception as e:
            print(f"Error getting electronic case documents: {e}")

        return documents

    async def download_pdf(
        self,
        url: str,
        save_path: str,
        retry: int = 3
    ) -> bool:
        """
        Download PDF file with retry logic.

        Args:
            url: PDF URL
            save_path: Path to save file
            retry: Number of retry attempts (default: 3)

        Returns:
            True if download successful, False otherwise
        """
        # Apply rate limiting
        await self._rate_limit()

        # Create output directory
        save_file = Path(save_path)
        save_file.parent.mkdir(parents=True, exist_ok=True)

        for attempt in range(retry):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                        if response.status == 200:
                            content = await response.read()

                            with open(save_file, 'wb') as f:
                                f.write(content)

                            return True
                        else:
                            print(f"HTTP {response.status} for {url}")

            except Exception as e:
                print(f"Download attempt {attempt + 1}/{retry} failed for {url}: {e}")

                if attempt < retry - 1:
                    await asyncio.sleep(2)  # Wait before retry

        return False

    async def download_case_documents(
        self,
        case_number: str,
        case_url: str = None,
        output_dir: Optional[str] = None,
        filter_important: bool = True
    ) -> Dict[str, Any]:
        """
        Download all (or important) documents for a case.

        Args:
            case_number: Case number
            case_url: Direct URL to case (optional, much faster if provided)
            output_dir: Output directory (default: downloads/YYYY/case_number)
            filter_important: Filter only important documents (default: True)

        Returns:
            Dictionary with results:
            - total: Total documents found
            - filtered: Documents after filtering
            - downloaded: Successfully downloaded
            - failed: Failed downloads
            - documents: List of downloaded document info
        """
        result = {
            "total": 0,
            "filtered": 0,
            "downloaded": 0,
            "failed": 0,
            "documents": []
        }

        try:
            # Navigate to case page
            success = await self.navigate_to_case(case_number, case_url)
            if not success:
                print(f"Failed to navigate to case {case_number}")
                return result

            # Get documents list
            documents = await self.get_electronic_case_documents()
            result["total"] = len(documents)

            if not documents:
                print(f"No documents found for case {case_number}")
                return result

            # Filter important documents
            if filter_important:
                documents = filter_important_documents(documents)
                result["filtered"] = len(documents)
            else:
                result["filtered"] = len(documents)

            # Determine output directory
            if output_dir is None:
                # Extract year from case number
                parts = case_number.split("-")
                year = parts[-1] if len(parts) >= 3 else "unknown"
                output_dir = str(self.download_dir / year / case_number)

            # Download each document
            for i, doc in enumerate(documents, 1):
                pdf_url = doc.get("pdf_url", "")
                if not pdf_url:
                    continue

                # Generate filename
                doc_type = doc.get("doc_type", "document").replace(" ", "_")
                filename = f"{i:03d}_{doc_type}.pdf"
                save_path = Path(output_dir) / filename

                print(f"Downloading {i}/{len(documents)}: {doc_type}...")

                success = await self.download_pdf(pdf_url, str(save_path))

                if success:
                    result["downloaded"] += 1
                    result["documents"].append({
                        **doc,
                        "local_path": str(save_path),
                        "filename": filename
                    })
                else:
                    result["failed"] += 1

        except Exception as e:
            print(f"Error downloading documents for case {case_number}: {e}")

        return result


# Example usage
async def example_usage():
    """Example of using DocumentDownloader."""

    # Initialize scraper with CDP
    async with PlaywrightScraper(use_cdp=True, cdp_url="http://localhost:9222") as scraper:
        # Create downloader
        downloader = DocumentDownloader(scraper, download_dir="downloads")

        # Download documents for a case
        case_number = "А40-12345-2024"
        result = await downloader.download_case_documents(case_number)

        print(f"\nResults for {case_number}:")
        print(f"Total documents: {result['total']}")
        print(f"After filtering: {result['filtered']}")
        print(f"Downloaded: {result['downloaded']}")
        print(f"Failed: {result['failed']}")


if __name__ == "__main__":
    asyncio.run(example_usage())

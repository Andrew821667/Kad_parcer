"""
Playwright-based scraper for КАД Арбитр.

This module bypasses HTTP 451 rate limiting by using real browser automation
with form filling (not direct API calls).

Based on working solutions from GitHub (Semendilov/kad-project and others).
"""

from __future__ import annotations

import asyncio
import random
from datetime import date, datetime
from typing import Any

from bs4 import BeautifulSoup
from playwright.async_api import Browser, Page, async_playwright
from structlog import get_logger

from src.scraper.court_names import get_court_full_name

logger = get_logger(__name__)


class PlaywrightScraper:
    """
    Browser-based scraper that bypasses КАД Арбитр protection.

    Uses Playwright to fill web forms and parse results, avoiding HTTP 451 errors
    that occur with direct API requests.
    """

    def __init__(
        self,
        headless: bool = True,
        browser_type: str = "firefox",
        base_delay: tuple[float, float] = (3.0, 5.0),
    ) -> None:
        """
        Initialize Playwright scraper.

        Args:
            headless: Run browser in headless mode
            browser_type: Browser to use ('firefox', 'chromium', 'webkit')
            base_delay: Min/max random delay in seconds between requests
        """
        self.headless = headless
        self.browser_type = browser_type
        self.base_delay = base_delay
        self.playwright = None
        self.browser: Browser | None = None
        self.page: Page | None = None

    async def __aenter__(self) -> PlaywrightScraper:
        """Context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        await self.close()

    async def start(self) -> None:
        """Start browser instance."""
        logger.info(
            "starting_playwright_browser",
            browser_type=self.browser_type,
            headless=self.headless,
        )

        self.playwright = await async_playwright().start()

        # Select browser
        if self.browser_type == "firefox":
            browser_launcher = self.playwright.firefox
        elif self.browser_type == "chromium":
            browser_launcher = self.playwright.chromium
        elif self.browser_type == "webkit":
            browser_launcher = self.playwright.webkit
        else:
            msg = f"Unknown browser type: {self.browser_type}"
            raise ValueError(msg)

        # Launch browser
        self.browser = await browser_launcher.launch(headless=self.headless)
        self.page = await self.browser.new_page()

        logger.info("playwright_browser_started")

    async def close(self) -> None:
        """Close browser and cleanup."""
        if self.page:
            await self.page.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

        logger.info("playwright_browser_closed")

    async def _random_delay(self) -> None:
        """Random delay to mimic human behavior and avoid rate limiting."""
        delay = random.uniform(*self.base_delay)
        logger.debug("applying_delay", delay_seconds=delay)
        await asyncio.sleep(delay)

    async def search_by_court_and_date(
        self,
        court_code: str,
        date_from: date | str,
        date_to: date | str,
        participant: str = "",
        judge: str = "",
        case_number: str = "",
    ) -> list[dict[str, Any]]:
        """
        Search cases by court and date range using web form.

        Args:
            court_code: Court code (e.g. 'А40', 'А41')
            date_from: Start date (YYYY-MM-DD or DD.MM.YYYY)
            date_to: End date (YYYY-MM-DD or DD.MM.YYYY)
            participant: Participant name (optional)
            judge: Judge name (optional)
            case_number: Case number (optional)

        Returns:
            List of case dictionaries

        Raises:
            RuntimeError: If browser not started
        """
        if not self.page:
            msg = "Browser not started. Call start() first or use context manager."
            raise RuntimeError(msg)

        # Format dates
        date_from_str = self._format_date(date_from)
        date_to_str = self._format_date(date_to)

        logger.info(
            "searching_cases",
            court_code=court_code,
            date_from=date_from_str,
            date_to=date_to_str,
            participant=participant,
            judge=judge,
            case_number=case_number,
        )

        # 1. Navigate to КАД Арбитр
        await self.page.goto("https://kad.arbitr.ru", wait_until="networkidle")
        await asyncio.sleep(2)

        # 2. Close popup if present
        try:
            await self.page.keyboard.press("Escape")
            await asyncio.sleep(1)
        except Exception as e:
            logger.debug("no_popup_to_close", error=str(e))

        # 3. Fill form
        # Convert court code to full name if provided
        court_full_name = None
        if court_code:
            try:
                court_full_name = get_court_full_name(court_code)
                logger.info("using_court_name", code=court_code, name=court_full_name)
            except ValueError as e:
                logger.warning("unknown_court_code", error=str(e))

        # Fill form fields using actual placeholders from kad.arbitr.ru
        if participant:
            await self.page.fill('textarea[placeholder="название, ИНН или ОГРН"]', participant)

        if judge:
            await self.page.fill('input[placeholder="фамилия судьи"]', judge)

        if court_full_name:
            # Court field with autocomplete
            await self.page.fill('input[placeholder="название суда"]', court_full_name)
            await asyncio.sleep(0.5)  # Wait for autocomplete dropdown
            await self.page.keyboard.press("Enter")  # Select first match

        if case_number:
            await self.page.fill('input[placeholder="например, А50-5568/08"]', case_number)

        # Date fields - both have same placeholder, use nth selector
        date_inputs = await self.page.query_selector_all('input[placeholder="дд.мм.гггг"]')
        if len(date_inputs) >= 2:
            await date_inputs[0].fill(date_from_str)  # First date field (from)
            await date_inputs[1].fill(date_to_str)    # Second date field (to)

        # Close date picker by clicking elsewhere or pressing Escape
        await self.page.keyboard.press("Escape")  # Close datepicker popup
        await asyncio.sleep(0.5)

        # Click somewhere safe to ensure datepicker is closed
        await self.page.click("body")  # Click on body to dismiss any popups
        await asyncio.sleep(0.5)

        # 4. Submit form
        await self.page.click("#b-form-submit")  # Use # for ID selector

        # 5. Wait for results
        await self._random_delay()

        # 6. Get total pages count
        try:
            total_pages_input = await self.page.query_selector("input#documentsPagesCount")
            if not total_pages_input:
                logger.warning("no_results_found")
                return []

            total_pages_str = await total_pages_input.get_attribute("value")
            total_pages = int(total_pages_str) if total_pages_str else 0

            logger.info("found_pages", total_pages=total_pages)
        except Exception as e:
            logger.error("failed_to_get_pages_count", error=str(e))
            return []

        # 7. Parse all pages
        results = []
        for page_num in range(1, total_pages + 1):
            # Navigate to page (skip for first page)
            if page_num > 1:
                try:
                    await self.page.click(f'id=pages >> a[href="#page{page_num}"]')
                    await self._random_delay()
                except Exception as e:
                    logger.error("failed_to_navigate_to_page", page=page_num, error=str(e))
                    continue

            # Parse current page
            try:
                page_cases = await self._parse_current_page()
                results.extend(page_cases)
                logger.info("parsed_page", page=page_num, cases_count=len(page_cases))
            except Exception as e:
                logger.error("failed_to_parse_page", page=page_num, error=str(e))

        logger.info(
            "search_completed",
            court_code=court_code,
            total_cases=len(results),
        )

        return results

    async def _parse_current_page(self) -> list[dict[str, Any]]:
        """
        Parse cases table from current page.

        Returns:
            List of case dictionaries
        """
        if not self.page:
            return []

        # Get table HTML
        try:
            table = await self.page.query_selector("table#b-cases")
            if not table:
                logger.warning("table_not_found")
                return []

            table_html = await table.inner_html()
        except Exception as e:
            logger.error("failed_to_get_table_html", error=str(e))
            return []

        # Parse with BeautifulSoup
        return self._parse_table_html(table_html)

    def _parse_table_html(self, html: str) -> list[dict[str, Any]]:
        """
        Parse cases from HTML table.

        Args:
            html: Table HTML

        Returns:
            List of case dictionaries
        """
        soup = BeautifulSoup(html, "lxml")
        rows = soup.find_all("tr")

        results = []
        for row in rows:
            try:
                # Extract case type
                case_type_div = row.find("td", class_="num")
                if not case_type_div:
                    continue

                delotype_div = case_type_div.find("div", class_="b-container").find("div")
                case_type = delotype_div.get("class")[0] if delotype_div else "unknown"

                # Extract case number and URL
                case_num_link = case_type_div.find("a", class_="num_case")
                if not case_num_link:
                    continue

                case_number = ";".join(case_type_div.text.replace("\n", "").split())
                case_url = case_num_link.get("href", "")

                # Extract court
                court_td = row.find("td", class_="court")
                court = ";".join(court_td.text.replace("\n", "").split()) if court_td else ""

                # Extract plaintiff
                plaintiff_td = row.find("td", class_="plaintiff")
                plaintiff = ""
                if plaintiff_td:
                    try:
                        plaintiff_span = plaintiff_td.find("span", class_="js-rolloverHtml")
                        if plaintiff_span:
                            plaintiff_parts = [
                                p.strip() for p in plaintiff_span.text.split("\n")
                            ]
                            plaintiff = ";".join(filter(None, plaintiff_parts))
                    except Exception:
                        pass

                # Extract respondent(s)
                respondent_td = row.find("td", class_="respondent")
                respondents = []
                if respondent_td:
                    try:
                        respondent_spans = respondent_td.find_all("span", class_="js-rolloverHtml")
                        for span in respondent_spans:
                            resp_parts = [p.strip() for p in span.text.split("\n")]
                            resp_text = ";".join(filter(None, resp_parts))
                            if resp_text:
                                respondents.append(resp_text)
                    except Exception:
                        pass

                # Build result dictionary
                case_data = {
                    "case_type": case_type,
                    "case_number": case_number,
                    "url": case_url,
                    "court": court,
                    "plaintiff": plaintiff,
                    "respondents": respondents,
                }

                results.append(case_data)

            except Exception as e:
                logger.warning("failed_to_parse_row", error=str(e))
                continue

        return results

    @staticmethod
    def _format_date(d: date | str) -> str:
        """
        Format date to DD.MM.YYYY for КАД Арбитр form.

        Args:
            d: Date object or string (YYYY-MM-DD or DD.MM.YYYY)

        Returns:
            Date string in DD.MM.YYYY format
        """
        if isinstance(d, date):
            return d.strftime("%d.%m.%Y")

        # If already in DD.MM.YYYY format
        if "." in d:
            return d

        # If in YYYY-MM-DD format
        try:
            dt = datetime.strptime(d, "%Y-%m-%d")
            return dt.strftime("%d.%m.%Y")
        except ValueError:
            # Return as-is if can't parse
            return d

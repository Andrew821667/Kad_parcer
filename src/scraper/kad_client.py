"""Client for interacting with KAD Arbitr internal API."""

import asyncio
import json
from pathlib import Path
from typing import Any, Optional

import httpx
from httpx import Response

from src.core.config import get_settings
from src.core.exceptions import ConnectionException, RateLimitException, ScraperException
from src.core.logging import get_logger
from src.scraper.rate_limiter import get_rate_limiter

settings = get_settings()
logger = get_logger(__name__)


class KadArbitrClient:
    """Client for KAD Arbitr internal API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
        cookies: Optional[dict[str, str]] = None,
    ) -> None:
        """Initialize KAD client.

        Args:
            base_url: Base URL for KAD (default from settings)
            timeout: Request timeout in seconds (default from settings)
            max_retries: Maximum number of retries (default from settings)
            cookies: Browser cookies for bypassing protection (optional)
        """
        self.base_url = base_url or settings.kad_base_url
        self.timeout = timeout or settings.scraper_timeout
        self.max_retries = max_retries or settings.scraper_max_retries
        self.rate_limiter = get_rate_limiter()
        self.cookies = cookies or {}

        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "KadArbitrClient":
        """Enter async context manager."""
        await self._ensure_client()
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Exit async context manager."""
        await self.close()

    async def _ensure_client(self) -> None:
        """Ensure HTTP client is initialized."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={
                    "User-Agent": settings.scraper_user_agent,
                    "Accept": "*/*",
                    "Content-Type": "application/json",
                    "x-date-format": "iso",  # Формат дат в ответе (из реального API)
                    "X-Requested-With": "XMLHttpRequest",  # AJAX идентификация
                },
                cookies=self.cookies,  # Используем cookies из браузера
                follow_redirects=True,
            )

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @staticmethod
    def load_cookies_from_playwright(cookies_file: str | Path) -> dict[str, str]:
        """Load cookies from Playwright JSON file.

        Args:
            cookies_file: Path to cookies JSON file from Playwright

        Returns:
            Dictionary of cookies {name: value}

        Example:
            cookies = KadArbitrClient.load_cookies_from_playwright("/tmp/kad_cookies.json")
            client = KadArbitrClient(cookies=cookies)
        """
        cookies_path = Path(cookies_file)
        if not cookies_path.exists():
            logger.warning(f"Cookies file not found: {cookies_path}")
            return {}

        try:
            with open(cookies_path, "r", encoding="utf-8") as f:
                playwright_cookies = json.load(f)

            # Конвертируем Playwright формат в httpx формат
            cookies_dict = {}
            for cookie in playwright_cookies:
                # Фильтруем cookies только для kad.arbitr.ru
                domain = cookie.get("domain", "")
                if "arbitr.ru" in domain:
                    cookies_dict[cookie["name"]] = cookie["value"]

            logger.info(f"Loaded {len(cookies_dict)} cookies from {cookies_path}")
            return cookies_dict

        except Exception as e:
            logger.error(f"Failed to load cookies: {e}")
            return {}

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> Response:
        """Make HTTP request with retry logic.

        Args:
            method: HTTP method
            url: Request URL
            **kwargs: Additional arguments for httpx

        Returns:
            HTTP response

        Raises:
            ConnectionException: If request fails after retries
            RateLimitException: If rate limited by server
        """
        await self._ensure_client()
        assert self._client is not None

        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                # Apply rate limiting
                await self.rate_limiter.acquire()

                logger.debug(
                    "making_request",
                    method=method,
                    url=url,
                    attempt=attempt + 1,
                )

                response = await self._client.request(method, url, **kwargs)

                # Check for rate limiting
                if response.status_code == 429:
                    logger.warning("rate_limited_by_server", url=url)
                    raise RateLimitException("Rate limited by server")

                # Check for success
                response.raise_for_status()

                logger.debug(
                    "request_success",
                    method=method,
                    url=url,
                    status=response.status_code,
                )

                return response

            except httpx.HTTPStatusError as e:
                last_error = e
                logger.warning(
                    "http_error",
                    method=method,
                    url=url,
                    status=e.response.status_code,
                    attempt=attempt + 1,
                )

                # Don't retry on 4xx errors (except 429)
                if 400 <= e.response.status_code < 500 and e.response.status_code != 429:
                    raise ScraperException(
                        f"HTTP error {e.response.status_code}",
                        details={"url": url, "status": e.response.status_code},
                    ) from e

            except (httpx.RequestError, httpx.TimeoutException) as e:
                last_error = e
                logger.warning(
                    "request_error",
                    method=method,
                    url=url,
                    error=str(e),
                    attempt=attempt + 1,
                )

            # Exponential backoff
            if attempt < self.max_retries - 1:
                wait_time = 2 ** attempt
                logger.debug("retrying_request", wait_time=wait_time)
                await asyncio.sleep(wait_time)

        # All retries exhausted
        raise ConnectionException(
            f"Failed after {self.max_retries} attempts",
            details={"url": url, "last_error": str(last_error)},
        ) from last_error

    async def search_cases(
        self,
        case_number: Optional[str] = None,
        participant_name: Optional[str] = None,
        court: Optional[str] = None,
        judge: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        case_type: Optional[str] = None,
        page: int = 1,
        count: int = 25,
    ) -> dict[str, Any]:
        """Search for cases using internal API.

        Args:
            case_number: Case number to search
            participant_name: Participant name
            court: Court name
            judge: Judge name
            date_from: Start date (ISO format)
            date_to: End date (ISO format)
            case_type: Case type (A, G, B)
            page: Page number
            count: Items per page

        Returns:
            Search results as dict

        Raises:
            ScraperException: If search fails
        """
        payload: dict[str, Any] = {
            "Page": page,
            "Count": count,
        }

        if case_number:
            # CaseNumbers должен быть массивом согласно API КАД
            payload["CaseNumbers"] = [case_number] if isinstance(case_number, str) else case_number

        if participant_name:
            payload["Sides"] = [
                {
                    "Name": participant_name,
                    "Type": None,
                    "ExactMatch": False,
                }
            ]

        if court:
            payload["Courts"] = [court]

        if judge:
            payload["Judges"] = [judge]

        if date_from:
            payload["DateFrom"] = date_from

        if date_to:
            payload["DateTo"] = date_to

        if case_type:
            payload["CaseType"] = case_type

        logger.info("searching_cases", payload=payload)

        try:
            response = await self._request_with_retry(
                "POST",
                "/Kad/SearchInstances",
                json=payload,
            )

            data = response.json()
            logger.info(
                "search_complete",
                total_count=data.get("Result", {}).get("TotalCount", 0),
                page=page,
            )

            return data

        except Exception as e:
            logger.error("search_failed", error=str(e), payload=payload)
            raise ScraperException(f"Search failed: {e}") from e

    async def get_case_card(self, case_id: str) -> str:
        """Get case card HTML.

        Args:
            case_id: Case ID from KAD

        Returns:
            HTML content of case card

        Raises:
            ScraperException: If request fails
        """
        logger.info("fetching_case_card", case_id=case_id)

        try:
            response = await self._request_with_retry(
                "GET",
                f"/Card/{case_id}",
            )

            logger.info("case_card_fetched", case_id=case_id, size=len(response.text))
            return response.text

        except Exception as e:
            logger.error("case_card_fetch_failed", case_id=case_id, error=str(e))
            raise ScraperException(f"Failed to fetch case card: {e}") from e

    async def download_document(self, document_url: str) -> bytes:
        """Download document from KAD.

        Args:
            document_url: Document URL

        Returns:
            Document content as bytes

        Raises:
            ScraperException: If download fails
        """
        logger.info("downloading_document", url=document_url)

        try:
            response = await self._request_with_retry(
                "GET",
                document_url,
            )

            logger.info("document_downloaded", url=document_url, size=len(response.content))
            return response.content

        except Exception as e:
            logger.error("document_download_failed", url=document_url, error=str(e))
            raise ScraperException(f"Failed to download document: {e}") from e

    async def search_by_court_and_date(
        self,
        court_code: str,
        date_from: str,
        date_to: str,
        page: int = 1,
        count: int = 100,
    ) -> dict[str, Any]:
        """Search cases by court and date range.

        Args:
            court_code: Court code (e.g., "А40", "Ф05", "09АП")
            date_from: Start date (ISO format: "2024-01-01")
            date_to: End date (ISO format: "2024-12-31")
            page: Page number
            count: Items per page (max unclear, test with 100)

        Returns:
            Search results as dict

        Raises:
            ScraperException: If search fails

        Example:
            >>> async with KadArbitrClient() as client:
            ...     # Поиск дел АС Москвы за декабрь 2024
            ...     results = await client.search_by_court_and_date(
            ...         court_code="А40",
            ...         date_from="2024-12-01",
            ...         date_to="2024-12-31",
            ...         count=100
            ...     )
            ...     print(f"Найдено дел: {results['Result']['TotalCount']}")
        """
        payload = {
            "Page": page,
            "Count": count,
            "Courts": [court_code],
            "DateFrom": date_from,
            "DateTo": date_to,
        }

        logger.info(
            "searching_by_court_and_date",
            court=court_code,
            date_from=date_from,
            date_to=date_to,
            page=page,
        )

        try:
            response = await self._request_with_retry(
                "POST",
                "/Kad/SearchInstances",
                json=payload,
            )

            data = response.json()
            logger.info(
                "court_date_search_complete",
                total_count=data.get("Result", {}).get("TotalCount", 0),
                court=court_code,
                page=page,
            )

            return data

        except Exception as e:
            logger.error(
                "court_date_search_failed",
                error=str(e),
                court=court_code,
                date_from=date_from,
                date_to=date_to,
            )
            raise ScraperException(f"Court date search failed: {e}") from e

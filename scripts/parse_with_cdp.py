#!/usr/bin/env python3
"""
Parse КАД Арбитр using CDP connection to real Chrome.

This script connects to Chrome running with --remote-debugging-port=9222
and uses it for scraping. This bypasses ALL bot detection.

BEFORE running:
1. Start Chrome with: ./scripts/start_chrome_debug.sh
2. Then run this script
"""

import asyncio
from datetime import date

from structlog import get_logger

from src.scraper.playwright_scraper import PlaywrightScraper
from src.storage.database.base import get_db, init_db

logger = get_logger(__name__)


async def test_cdp_parsing():
    """Test parsing with CDP connection."""
    logger.info("starting_cdp_parsing_test")

    # Initialize database
    await init_db()

    # Create scraper with CDP connection
    async with PlaywrightScraper(
        use_cdp=True,  # Connect to existing Chrome
        cdp_url="http://localhost:9222",
    ) as scraper:
        logger.info("scraper_started_with_cdp")

        # Test search for January 2024
        logger.info("searching_cases", date_from="2024-01-01", date_to="2024-01-31")

        cases = await scraper.search_cases(
            court_code=None,  # No court filter (search all courts)
            date_from=date(2024, 1, 1),
            date_to=date(2024, 1, 31),
            participant=None,
            judge=None,
            case_number=None,
        )

        logger.info(
            "search_completed",
            cases_found=len(cases),
            first_case=cases[0] if cases else None,
        )

        # Save to database
        if cases:
            logger.info("saving_cases_to_database", count=len(cases))

            async for session in get_db():
                try:
                    for case_dict in cases:
                        # TODO: Add proper save logic
                        logger.info("case_data", case=case_dict)
                finally:
                    await session.close()

        logger.info("cdp_parsing_test_completed", total_cases=len(cases))


if __name__ == "__main__":
    print("🔗 Парсинг через CDP подключение к реальному Chrome")
    print("")
    print("⚠️  Убедитесь что Chrome запущен с remote debugging!")
    print("   Команда: ./scripts/start_chrome_debug.sh")
    print("")

    asyncio.run(test_cdp_parsing())

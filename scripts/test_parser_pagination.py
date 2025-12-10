#!/usr/bin/env python3
"""
Test parser with CDP and pagination for 2-3 pages.
"""

import asyncio
from datetime import date

from structlog import get_logger

from src.scraper.playwright_scraper import PlaywrightScraper

logger = get_logger(__name__)


async def test_parser_with_pagination():
    """Test parser with real Chrome via CDP."""
    print("🚀 Тест парсера с пагинацией через CDP\n")

    # Create scraper with CDP
    async with PlaywrightScraper(
        use_cdp=True,
        cdp_url="http://localhost:9222",
    ) as scraper:
        print("✅ Подключено к Chrome через CDP\n")

        # Search for January 2024 (limited to first 3 pages for testing)
        print("🔍 Поиск дел за январь 2024...")
        print("   (Ограничим 3 страницами для теста)\n")

        try:
            # Monkey-patch to limit pages for testing
            original_search = scraper.search_cases

            async def limited_search(*args, **kwargs):
                results = []
                # Do original form filling
                await scraper.page.goto("https://kad.arbitr.ru", wait_until="networkidle")
                await asyncio.sleep(2)

                # Close popup
                try:
                    await scraper.page.keyboard.press("Escape")
                    await asyncio.sleep(1)
                except Exception:
                    pass

                # Fill dates
                date_inputs = await scraper.page.query_selector_all('input[placeholder="дд.мм.гггг"]')
                if len(date_inputs) >= 2:
                    await date_inputs[0].click()
                    await asyncio.sleep(0.2)
                    await date_inputs[0].fill("01.01.2024")
                    await asyncio.sleep(0.5)

                    await date_inputs[1].click()
                    await asyncio.sleep(0.2)
                    await date_inputs[1].fill("31.01.2024")
                    await asyncio.sleep(0.5)

                await scraper.page.click("body")
                await asyncio.sleep(0.5)

                # Submit
                await scraper.page.click("#b-form-submit")
                await asyncio.sleep(5)

                # Get pages count
                total_pages_input = await scraper.page.query_selector("input#documentsPagesCount")
                if not total_pages_input:
                    print("❌ Таблица результатов не найдена")
                    return []

                total_pages_str = await total_pages_input.get_attribute("value")
                total_pages = int(total_pages_str) if total_pages_str else 0

                print(f"📄 Всего страниц: {total_pages}")
                print(f"📄 Будем парсить: 3 страницы (для теста)\n")

                # Parse first 3 pages
                for page_num in range(1, min(4, total_pages + 1)):
                    print(f"📖 Парсинг страницы {page_num}/3...")

                    # Navigate to page (skip for first)
                    if page_num > 1:
                        link = await scraper.page.query_selector(f'a[href="#page{page_num}"]')
                        if link:
                            await link.click()
                            await asyncio.sleep(5)
                            print(f"   ✓ Перешли на страницу {page_num}")
                        else:
                            print(f"   ✗ Ссылка на страницу {page_num} не найдена")
                            continue

                    # Parse current page
                    page_cases = await scraper._parse_current_page()
                    results.extend(page_cases)
                    print(f"   ✓ Найдено дел: {len(page_cases)}\n")

                return results

            # Run limited search
            cases = await limited_search()

            print("=" * 80)
            print(f"✅ ПАРСИНГ ЗАВЕРШЕН")
            print(f"   Всего дел спарсено: {len(cases)}")
            print(f"   Ожидалось: ~75 дел (3 страницы × 25)")
            print("=" * 80)

            if cases:
                print("\n📋 Первые 3 дела:")
                for i, case in enumerate(cases[:3], 1):
                    print(f"\n{i}. {case.get('case_number', 'N/A')}")
                    print(f"   Суд: {case.get('court', 'N/A')}")
                    print(f"   Дата: {case.get('date', 'N/A')}")

        except Exception as e:
            logger.error("test_failed", error=str(e))
            raise


if __name__ == "__main__":
    print("⚠️  Убедитесь что Chrome запущен с remote debugging!")
    print("   Команда: ./scripts/start_chrome_debug.sh\n")

    asyncio.run(test_parser_with_pagination())

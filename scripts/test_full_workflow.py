#!/usr/bin/env python3
"""
Test full workflow: parse 3 pages + download 5 court decisions.
"""

import asyncio
import random
from pathlib import Path

from structlog import get_logger

from src.scraper.playwright_scraper import PlaywrightScraper

logger = get_logger(__name__)


async def test_full_workflow():
    """Test complete workflow with document downloads."""
    print("🚀 Полный тест workflow: парсинг + скачивание актов\n")

    # Create scraper with CDP
    async with PlaywrightScraper(
        use_cdp=True,
        cdp_url="http://localhost:9222",
    ) as scraper:
        print("✅ Подключено к Chrome через CDP\n")

        # STEP 1: Parse 3 pages
        print("=" * 80)
        print("ШАГ 1: Парсинг 3 страниц")
        print("=" * 80)

        results = []

        # Navigate and search
        await scraper.page.goto("https://kad.arbitr.ru", wait_until="networkidle")
        await asyncio.sleep(2)

        # Close popup
        try:
            await scraper.page.keyboard.press("Escape")
            await asyncio.sleep(1)
        except Exception:
            pass

        # Fill dates
        date_inputs = await scraper.page.query_selector_all(
            'input[placeholder="дд.мм.гггг"]'
        )
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
        total_pages_input = await scraper.page.query_selector(
            "input#documentsPagesCount"
        )
        if not total_pages_input:
            print("❌ Таблица результатов не найдена")
            return

        total_pages_str = await total_pages_input.get_attribute("value")
        total_pages = int(total_pages_str) if total_pages_str else 0

        print(f"\n📄 Всего страниц: {total_pages}")
        print(f"📄 Будем парсить: 3 страницы\n")

        # Parse first 3 pages
        for page_num in range(1, min(4, total_pages + 1)):
            print(f"📖 Парсинг страницы {page_num}/3...")

            # Navigate to page (skip for first)
            if page_num > 1:
                link = await scraper.page.query_selector(f'a[href="#page{page_num}"]')
                if link:
                    await link.click()
                    await asyncio.sleep(5)

            # Parse current page
            page_cases = await scraper._parse_current_page()
            results.extend(page_cases)
            print(f"   ✓ Найдено дел: {len(page_cases)}")

        print(f"\n✅ Парсинг завершен: {len(results)} дел\n")

        # STEP 2: Select 5 random cases
        print("=" * 80)
        print("ШАГ 2: Выбор 5 случайных дел для скачивания актов")
        print("=" * 80)

        if len(results) < 5:
            print(f"❌ Недостаточно дел ({len(results)}), нужно минимум 5")
            return

        selected_cases = random.sample(results, 5)

        print("\n📋 Выбранные дела:")
        for i, case in enumerate(selected_cases, 1):
            print(f"{i}. {case['case_number']} - {case['case_date']}")
            print(f"   URL: {case['url']}")

        # STEP 3: Download documents
        print("\n" + "=" * 80)
        print("ШАГ 3: Скачивание судебных актов")
        print("=" * 80)

        # Setup download directory
        downloads_dir = Path.home() / "Downloads" / "kad_test"
        downloads_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n📁 Папка для скачивания: {downloads_dir}\n")

        downloaded_count = 0

        for i, case in enumerate(selected_cases, 1):
            print(f"📄 Дело {i}/5: {case['case_number']}")

            try:
                # Open case page in same tab
                await scraper.page.goto(case["url"], wait_until="networkidle")
                await asyncio.sleep(2)

                print(f"   ✓ Страница дела открыта")

                # Look for document download links
                # Common patterns on kad.arbitr.ru:
                # - Links with text "Судебный акт"
                # - Links to PDF files
                # - Download buttons

                # Try to find document links
                doc_links = await scraper.page.query_selector_all(
                    'a[href*=".pdf"], a:has-text("Судебный акт"), a:has-text("Скачать"), a.btn-download'
                )

                if not doc_links:
                    print(f"   ⚠️  Не найдены ссылки на документы")
                    continue

                print(f"   Найдено ссылок на документы: {len(doc_links)}")

                # Try to download first document
                first_link = doc_links[0]
                link_text = await first_link.inner_text()
                link_href = await first_link.get_attribute("href")

                print(f"   Пытаюсь скачать: {link_text[:50]} ({link_href[:50]}...)")

                # Setup download event listener
                async with scraper.page.expect_download(timeout=30000) as download_info:
                    await first_link.click()

                download = await download_info.value

                # Save file
                filename = f"{case['case_number'].replace('/', '_')}_{download.suggested_filename}"
                filepath = downloads_dir / filename

                await download.save_as(str(filepath))

                file_size = filepath.stat().st_size if filepath.exists() else 0

                print(f"   ✅ Скачан: {filename} ({file_size} bytes)")
                downloaded_count += 1

            except Exception as e:
                print(f"   ❌ Ошибка: {e}")
                continue

        # Summary
        print("\n" + "=" * 80)
        print("ИТОГИ")
        print("=" * 80)
        print(f"✅ Дел спарсено: {len(results)}")
        print(f"✅ Актов скачано: {downloaded_count}/5")
        print(f"📁 Папка: {downloads_dir}")
        print("=" * 80)

        if downloaded_count > 0:
            print(f"\n🎉 Успешно! Откройте папку и проверьте файлы:")
            print(f"   open {downloads_dir}")


if __name__ == "__main__":
    print("⚠️  Убедитесь что Chrome запущен с remote debugging!")
    print("   Команда: ./scripts/start_chrome_debug.sh\n")

    asyncio.run(test_full_workflow())

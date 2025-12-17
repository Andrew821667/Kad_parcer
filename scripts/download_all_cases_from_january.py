#!/usr/bin/env python3
"""
Скачивание документов для ВСЕХ дел из january_2024_cases.json.
Проходит по каждому делу, открывает вкладку "Электронное дело" и скачивает все документы.
"""

import asyncio
import json
from pathlib import Path

import httpx

from src.scraper.playwright_scraper import PlaywrightScraper


async def download_case_documents(scraper, case, base_downloads_dir):
    """Скачать все документы для одного дела."""

    case_number = case['case_number']
    case_url = case['url']

    # Нормализация URL
    case_url = case_url.replace('https//kad.arbitr.ru', '').replace('http//kad.arbitr.ru', '').replace('//kad.arbitr.ru', '').replace('https://kad.arbitr.ru', '').replace('http://kad.arbitr.ru', '').replace('https:/', '').replace('http:/', '')
    if not case_url.startswith('/'):
        case_url = '/' + case_url
    case_url = f"https://kad.arbitr.ru{case_url}"

    print(f"\n{'=' * 80}")
    print(f"📋 Дело: {case_number}")
    print(f"🔗 URL: {case_url}")
    print(f"{'=' * 80}\n")

    # Создать папку для дела
    case_folder = base_downloads_dir / case_number.replace('/', '_')
    case_folder.mkdir(parents=True, exist_ok=True)

    try:
        # Открыть страницу дела
        await scraper.page.goto(case_url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)

        # Найти и кликнуть на вкладку "Электронное дело"
        electronic_tab = await scraper.page.query_selector(".js-case-chrono-button--ed")

        if not electronic_tab:
            print("❌ Вкладка 'Электронное дело' не найдена - пропускаем дело\n")
            return {"case_number": case_number, "status": "no_tab", "documents": 0}

        await electronic_tab.click()
        await asyncio.sleep(3)

        # Получить cookies для скачивания
        cookies = await scraper.page.context.cookies()
        cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}

        total_downloaded = 0
        downloaded_urls = set()
        page_num = 1

        while True:
            # Найти все PDF на текущей странице
            pdf_links = await scraper.page.query_selector_all('a[href$=".pdf"]')

            if not pdf_links:
                break

            # Скачать каждый PDF
            for link in pdf_links:
                try:
                    text = await link.inner_text()
                    href = await link.get_attribute("href")

                    # Пропустить дубликаты
                    if href in downloaded_urls:
                        continue

                    downloaded_urls.add(href)

                    # Скачать с retry
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            async with httpx.AsyncClient(
                                cookies=cookie_dict,
                                timeout=30.0,
                                follow_redirects=True
                            ) as client:
                                response = await client.get(href)

                                if response.status_code == 200:
                                    content_type = response.headers.get('content-type', '')

                                    if 'pdf' in content_type.lower() or href.endswith('.pdf'):
                                        filename = href.split("/")[-1]
                                        if not filename.endswith('.pdf'):
                                            filename += '.pdf'

                                        filepath = case_folder / f"{total_downloaded + 1:03d}_{filename}"
                                        filepath.write_bytes(response.content)

                                        total_downloaded += 1
                                        break
                                    else:
                                        break

                                else:
                                    if attempt < max_retries - 1:
                                        await asyncio.sleep(2)
                                    break

                        except Exception as e:
                            if attempt < max_retries - 1:
                                await asyncio.sleep(2)
                            else:
                                pass  # Тихо пропускаем ошибки для массовой обработки

                except Exception:
                    pass  # Тихо пропускаем ошибки

            # Проверка следующей страницы
            next_button = await scraper.page.query_selector(".js-chrono-pagination-pager-item--arrow.next")
            if not next_button:
                next_button = await scraper.page.query_selector(".js-card-list_paginator-item.next")

            if not next_button:
                break

            try:
                is_disabled = await next_button.evaluate("el => el.classList.contains('disabled') || el.hasAttribute('disabled')")
                if is_disabled:
                    break
            except:
                pass

            try:
                await next_button.click()
                await asyncio.sleep(3)
                page_num += 1
            except:
                break

        print(f"✅ Скачано: {total_downloaded} документов")
        return {"case_number": case_number, "status": "success", "documents": total_downloaded}

    except Exception as e:
        print(f"❌ Ошибка при обработке дела: {str(e)[:100]}")
        return {"case_number": case_number, "status": "error", "documents": 0, "error": str(e)[:200]}


async def main():
    """Главная функция - обработать все дела."""

    print("=" * 80)
    print("МАССОВОЕ СКАЧИВАНИЕ ДОКУМЕНТОВ ИЗ JANUARY 2024")
    print("=" * 80)
    print()

    # Загрузить список дел
    cases_file = Path("data/january_2024_cases.json")
    if not cases_file.exists():
        print(f"❌ Файл {cases_file} не найден!")
        return

    with open(cases_file, encoding="utf-8") as f:
        all_cases = json.load(f)

    print(f"📊 Найдено дел: {len(all_cases)}\n")

    # Создать папку для скачивания
    downloads_dir = Path("downloads")
    downloads_dir.mkdir(exist_ok=True)

    # Результаты
    results = []
    total_docs = 0
    success_count = 0
    error_count = 0

    async with PlaywrightScraper(use_cdp=True, cdp_url="http://localhost:9222") as scraper:
        for i, case in enumerate(all_cases, 1):
            print(f"\n[{i}/{len(all_cases)}] Обработка дела...")

            result = await download_case_documents(scraper, case, downloads_dir)
            results.append(result)

            if result["status"] == "success":
                success_count += 1
                total_docs += result["documents"]
            else:
                error_count += 1

            # Небольшая пауза между делами
            await asyncio.sleep(1)

    # Сохранить результаты
    results_file = downloads_dir / "download_results.json"
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # Итоговая статистика
    print("\n" + "=" * 80)
    print("ИТОГОВАЯ СТАТИСТИКА")
    print("=" * 80)
    print()
    print(f"✅ Обработано дел: {len(all_cases)}")
    print(f"✅ Успешно: {success_count}")
    print(f"❌ Ошибок: {error_count}")
    print(f"📄 Всего документов скачано: {total_docs}")
    print(f"💾 Папка: {downloads_dir}")
    print(f"📋 Результаты сохранены: {results_file}")
    print()
    print("=" * 80)
    print("🎉 ОБРАБОТКА ЗАВЕРШЕНА!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())

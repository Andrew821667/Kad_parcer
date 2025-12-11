#!/usr/bin/env python3
"""
Скачивание ВСЕХ документов со вкладки "Электронное дело" с пагинацией.
Проходит по всем страницам и скачивает все PDF.
"""

import asyncio
import json
from pathlib import Path

import httpx

from src.scraper.playwright_scraper import PlaywrightScraper


async def download_all_documents_from_electronic_case():
    """Скачать все документы со вкладки Электронное дело."""

    print("=" * 80)
    print("СКАЧИВАНИЕ ВСЕХ ДОКУМЕНТОВ СО ВКЛАДКИ 'ЭЛЕКТРОННОЕ ДЕЛО'")
    print("=" * 80)
    print()

    # Загрузить тестовое дело
    cases_file = Path("data/january_2024_cases.json")
    with open(cases_file, encoding="utf-8") as f:
        all_cases = json.load(f)

    case = all_cases[0]
    case_url = case['url']

    # Нормализация URL
    case_url = case_url.replace('https//kad.arbitr.ru', '').replace('http//kad.arbitr.ru', '').replace('//kad.arbitr.ru', '').replace('https://kad.arbitr.ru', '').replace('http://kad.arbitr.ru', '').replace('https:/', '').replace('http:/', '')
    if not case_url.startswith('/'):
        case_url = '/' + case_url
    case_url = f"https://kad.arbitr.ru{case_url}"

    print(f"📋 Дело: {case['case_number']}")
    print(f"🔗 URL: {case_url}\n")

    # Создать папку для скачивания
    case_folder = Path("downloads") / case['case_number'].replace('/', '_')
    case_folder.mkdir(parents=True, exist_ok=True)

    async with PlaywrightScraper(use_cdp=True, cdp_url="http://localhost:9222") as scraper:
        await scraper.page.goto(case_url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)

        print("✅ Страница дела загружена\n")

        # ================================================================
        # 1. ПЕРЕХОД НА ВКЛАДКУ "ЭЛЕКТРОННОЕ ДЕЛО"
        # ================================================================

        print("=" * 80)
        print("ШАГ 1: Переход на вкладку 'Электронное дело'")
        print("=" * 80)
        print()

        electronic_tab = await scraper.page.query_selector(".js-case-chrono-button--ed")

        if not electronic_tab:
            print("❌ Вкладка 'Электронное дело' не найдена!")
            return

        print("✅ Вкладка найдена, кликаем...")
        await electronic_tab.click()
        await asyncio.sleep(3)  # Ждем загрузки содержимого
        print("✅ Вкладка загружена\n")

        # ================================================================
        # 2. СКАЧИВАНИЕ ДОКУМЕНТОВ СО ВСЕХ СТРАНИЦ
        # ================================================================

        print("=" * 80)
        print("ШАГ 2: Скачивание документов со всех страниц")
        print("=" * 80)
        print()

        # Получить cookies для скачивания
        cookies = await scraper.page.context.cookies()
        cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}

        page_num = 1
        total_downloaded = 0
        downloaded_urls = set()  # Для избежания дубликатов

        while True:
            print(f"📄 Страница {page_num}")
            print("-" * 80)

            # Найти все PDF на текущей странице
            pdf_links = await scraper.page.query_selector_all('a[href$=".pdf"]')
            print(f"   Найдено PDF ссылок: {len(pdf_links)}\n")

            if not pdf_links:
                print("   ⚠️  PDF не найдены на этой странице\n")
                break

            # Скачать каждый PDF
            page_downloaded = 0
            for i, link in enumerate(pdf_links, 1):
                try:
                    text = await link.inner_text()
                    href = await link.get_attribute("href")

                    # Пропустить если уже скачивали
                    if href in downloaded_urls:
                        continue

                    downloaded_urls.add(href)

                    print(f"   [{i}/{len(pdf_links)}] {text.strip()[:60]}")

                    # Скачать PDF через HTTP
                    async with httpx.AsyncClient(
                        cookies=cookie_dict,
                        timeout=30.0,
                        follow_redirects=True
                    ) as client:
                        response = await client.get(href)

                        if response.status_code == 200:
                            content_type = response.headers.get('content-type', '')

                            if 'pdf' in content_type.lower() or href.endswith('.pdf'):
                                # Извлечь имя файла из URL
                                filename = href.split("/")[-1]
                                if not filename.endswith('.pdf'):
                                    filename += '.pdf'

                                # Добавить номер для уникальности
                                filepath = case_folder / f"{total_downloaded + 1:03d}_{filename}"

                                filepath.write_bytes(response.content)

                                print(f"        ✅ {len(response.content)//1024} KB → {filepath.name}")
                                page_downloaded += 1
                                total_downloaded += 1
                            else:
                                print(f"        ⚠️  Не PDF: {content_type}")
                        else:
                            print(f"        ❌ HTTP {response.status_code}")

                except Exception as e:
                    print(f"        ❌ Ошибка: {str(e)[:60]}")

            print(f"\n   📊 Скачано на странице {page_num}: {page_downloaded} документов")
            print(f"   📊 Всего скачано: {total_downloaded} документов\n")

            # ================================================================
            # 3. ПРОВЕРКА НАЛИЧИЯ СЛЕДУЮЩЕЙ СТРАНИЦЫ
            # ================================================================

            # Искать кнопку "следующая страница"
            next_button = None

            # Вариант 1: .js-chrono-pagination-pager-item--arrow.next
            next_button = await scraper.page.query_selector(".js-chrono-pagination-pager-item--arrow.next")

            # Вариант 2: .js-card-list_paginator-item.next
            if not next_button:
                next_button = await scraper.page.query_selector(".js-card-list_paginator-item.next")

            if not next_button:
                print("   ℹ️  Следующая страница не найдена - это последняя страница\n")
                break

            # Проверить что кнопка активна (не disabled)
            try:
                is_disabled = await next_button.evaluate("el => el.classList.contains('disabled') || el.hasAttribute('disabled')")
                if is_disabled:
                    print("   ℹ️  Кнопка 'Следующая' неактивна - это последняя страница\n")
                    break
            except:
                pass

            # Кликнуть на следующую страницу
            print("   ➡️  Переход на следующую страницу...")
            try:
                await next_button.click()
                await asyncio.sleep(3)  # Ждем загрузки следующей страницы
                page_num += 1
                print("   ✅ Следующая страница загружена\n")
            except Exception as e:
                print(f"   ❌ Ошибка при переходе: {str(e)[:60]}\n")
                break

        # ================================================================
        # ИТОГИ
        # ================================================================

        print("=" * 80)
        print("ИТОГОВАЯ СТАТИСТИКА")
        print("=" * 80)
        print()
        print(f"✅ Дело: {case['case_number']}")
        print(f"✅ Страниц обработано: {page_num}")
        print(f"✅ Документов скачано: {total_downloaded}")
        print(f"✅ Папка: {case_folder}")
        print()
        print("=" * 80)
        print("🎉 СКАЧИВАНИЕ ЗАВЕРШЕНО!")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(download_all_documents_from_electronic_case())

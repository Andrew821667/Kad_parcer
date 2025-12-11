#!/usr/bin/env python3
"""
ФИНАЛЬНЫЙ парсер января 2024 - все 130к дел через фильтр по судам.
Стратегия: ДЕНЬ + СУД (31 день × ~100 судов = ~3100 запросов)
"""

import asyncio
import json
from pathlib import Path
from datetime import datetime, timedelta

from src.scraper.playwright_scraper import PlaywrightScraper


async def get_all_courts(scraper):
    """Получить список всех судов из <select id='Courts'>."""

    print("=" * 80)
    print("ПОЛУЧЕНИЕ СПИСКА СУДОВ")
    print("=" * 80)
    print()

    # Открыть главную страницу
    await scraper.page.goto("https://kad.arbitr.ru", wait_until="networkidle", timeout=30000)
    await asyncio.sleep(2)

    # Закрыть popup
    try:
        await scraper.page.keyboard.press("Escape")
        await asyncio.sleep(1)
    except:
        pass

    # Найти <select id="Courts">
    select_element = await scraper.page.query_selector('select#Courts, select[name="Courts"]')
    if not select_element:
        print("❌ <select id='Courts'> не найден")
        return []

    # Получить все <option> элементы
    options = await select_element.query_selector_all('option')

    courts = []
    for option in options:
        try:
            court_name = await option.inner_text()
            court_name = court_name.strip()
            if court_name and len(court_name) > 3:  # Пропустить пустые
                courts.append(court_name)
        except:
            pass

    print(f"✅ Найдено судов: {len(courts)}")
    print()
    print("Первые 10 судов:")
    for i, court in enumerate(courts[:10], 1):
        print(f"  {i}. {court}")
    print()

    return courts


async def parse_day_court(scraper, day: datetime, court_name: str):
    """Парсинг одного дня для одного суда."""

    day_str = day.strftime("%d.%m.%Y")
    day_label = day.strftime("%Y-%m-%d")

    print(f"  📅 {day_label} | 🏛️  {court_name[:40]}")

    # Открыть главную страницу
    await scraper.page.goto("https://kad.arbitr.ru", wait_until="networkidle", timeout=30000)
    await asyncio.sleep(1)

    # Закрыть popup
    try:
        await scraper.page.keyboard.press("Escape")
        await asyncio.sleep(0.5)
    except:
        pass

    # Заполнить даты
    date_inputs = await scraper.page.query_selector_all('input[placeholder="дд.мм.гггг"]')
    if len(date_inputs) >= 2:
        # Дата С
        await date_inputs[0].click()
        await asyncio.sleep(0.2)
        await date_inputs[0].fill(day_str)
        await asyncio.sleep(0.2)
        # Закрыть datepicker - кликнуть на заголовок формы
        await scraper.page.click("h1, .b-form-title", force=True)
        await asyncio.sleep(0.3)

        # Дата ПО
        await date_inputs[1].click()
        await asyncio.sleep(0.2)
        await date_inputs[1].fill(day_str)
        await asyncio.sleep(0.2)
        # Закрыть datepicker - кликнуть на заголовок формы
        await scraper.page.click("h1, .b-form-title", force=True)
        await asyncio.sleep(0.3)

    # Выбрать суд из <select>
    select_element = await scraper.page.query_selector('select#Courts')
    if select_element:
        # Найти опцию с нужным названием суда и выбрать ее
        await select_element.evaluate(f"""(select, courtName) => {{
            const options = Array.from(select.options);
            const option = options.find(opt => opt.text.trim() === courtName);
            if (option) {{
                select.value = option.value;
                // Триггернуть событие change
                select.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }}
        }}""", court_name)
        await asyncio.sleep(0.5)

    # Нажать "Найти"
    await scraper.page.click("#b-form-submit")
    await asyncio.sleep(4)

    # Проверить результаты
    total_pages_input = await scraper.page.query_selector("input#documentsPagesCount")
    if not total_pages_input:
        print(f"     ⚠️  Нет результатов")
        return []

    total_pages_str = await total_pages_input.get_attribute("value")
    total_pages = int(total_pages_str) if total_pages_str else 0

    if total_pages == 0:
        print(f"     ℹ️  0 страниц")
        return []

    if total_pages >= 40:
        print(f"     ⚠️  ЛИМИТ! {total_pages} страниц (пропускаем)")
        return []

    # Парсить все страницы
    all_cases = []

    for page_num in range(1, total_pages + 1):
        try:
            cases = await scraper._parse_current_page()
            all_cases.extend(cases)

            # Переход на следующую страницу
            if page_num < total_pages:
                link = await scraper.page.query_selector(f'a[href="#page{page_num + 1}"]')
                if link:
                    await link.click()
                    await asyncio.sleep(2)
                else:
                    break
        except Exception as e:
            print(f"     ❌ Ошибка на странице {page_num}")
            continue

    print(f"     ✅ {len(all_cases)} дел")
    return all_cases


async def main():
    """Главная функция."""

    print("=" * 80)
    print("🚀 ФИНАЛЬНЫЙ ПАРСИНГ ЯНВАРЯ 2024")
    print("   Стратегия: ДЕНЬ + СУД")
    print("=" * 80)
    print()

    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    async with PlaywrightScraper(use_cdp=True, cdp_url="http://localhost:9222") as scraper:
        print("✅ Подключено к Chrome\n")

        # Получить список всех судов
        courts = await get_all_courts(scraper)

        if not courts:
            print("❌ Не удалось получить список судов!")
            return

        print(f"📊 План: 30 дней (без 1 января) × {len(courts)} судов = {30 * len(courts)} запросов\n")

        input("⏸️  Нажмите Enter чтобы начать парсинг...")
        print()

        all_cases = []
        start_time = datetime.now()

        # Парсить каждый день (пропускаем 1 января - праздник!)
        for day_num in range(2, 32):  # Со 2 по 31 января
            day = datetime(2024, 1, day_num)
            day_str = day.strftime("%d.%m.%Y")

            print(f"\n{'=' * 80}")
            print(f"ДЕНЬ {day_num}/31: {day_str}")
            print(f"{'=' * 80}")

            day_cases = []

            # Парсить каждый суд
            for court_idx, court_name in enumerate(courts, 1):
                print(f"[{court_idx}/{len(courts)}]", end=" ")

                try:
                    cases = await parse_day_court(scraper, day, court_name)
                    day_cases.extend(cases)
                except Exception as e:
                    print(f"     ❌ Ошибка: {str(e)[:50]}")

                await asyncio.sleep(0.5)

            all_cases.extend(day_cases)

            print(f"\n📊 День {day_num}: {len(day_cases)} дел | Всего: {len(all_cases)}")

            # Сохранять каждые 3 дня
            if day_num % 3 == 0:
                temp_file = data_dir / f"january_2024_cases_day{day_num}.json"
                temp_file.write_text(
                    json.dumps(all_cases, ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )
                print(f"💾 Сохранено: {temp_file}")

        # Финальное сохранение
        final_file = data_dir / "january_2024_FULL_ALL_cases.json"
        final_file.write_text(
            json.dumps(all_cases, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        elapsed = (datetime.now() - start_time).total_seconds()

        print(f"\n{'=' * 80}")
        print("🎉 ПАРСИНГ ЗАВЕРШЕН!")
        print(f"{'=' * 80}")
        print()
        print(f"✅ Всего дел: {len(all_cases):,}")
        print(f"⏱️  Время: {elapsed/3600:.1f} часов")
        print(f"💾 Файл: {final_file}")
        print()


if __name__ == "__main__":
    asyncio.run(main())

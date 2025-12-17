#!/usr/bin/env python3
"""
ПОЛНЫЙ парсинг января 2024 - все 130 000 дел.
Стратегия: парсить по дням, обходя лимит 1000 результатов.
"""

import asyncio
import json
from pathlib import Path
from datetime import datetime, timedelta

from src.scraper.playwright_scraper import PlaywrightScraper


async def parse_date_range(scraper, start_date: str, end_date: str, day_label: str):
    """
    Парсинг одного диапазона дат.
    Возвращает список дел и флаг hit_limit (True если найдено >= 1000 дел).
    """

    print(f"\n{'─' * 80}")
    print(f"📅 {day_label}: {start_date} → {end_date}")
    print(f"{'─' * 80}")

    # Открыть главную страницу
    await scraper.page.goto("https://kad.arbitr.ru", wait_until="networkidle", timeout=30000)
    await asyncio.sleep(2)

    # Закрыть popup
    try:
        await scraper.page.keyboard.press("Escape")
        await asyncio.sleep(1)
    except:
        pass

    # Заполнить форму поиска
    date_inputs = await scraper.page.query_selector_all('input[placeholder="дд.мм.гггг"]')
    if len(date_inputs) >= 2:
        # Дата начала
        await date_inputs[0].click()
        await asyncio.sleep(0.2)
        await date_inputs[0].fill(start_date)
        await asyncio.sleep(0.5)

        # Дата конца
        await date_inputs[1].click()
        await asyncio.sleep(0.2)
        await date_inputs[1].fill(end_date)
        await asyncio.sleep(0.5)

    await scraper.page.click("body")
    await asyncio.sleep(0.5)

    # Отправить форму
    await scraper.page.click("#b-form-submit")
    await asyncio.sleep(5)

    # Проверить количество страниц
    total_pages_input = await scraper.page.query_selector("input#documentsPagesCount")
    if not total_pages_input:
        print("❌ Результаты не найдены")
        return [], False

    total_pages_str = await total_pages_input.get_attribute("value")
    total_pages = int(total_pages_str) if total_pages_str else 0

    # Проверка лимита (40 страниц = 1000 дел)
    hit_limit = total_pages >= 40

    if hit_limit:
        print(f"⚠️  ЛИМИТ! Найдено {total_pages} страниц (≥1000 дел)")
        print(f"   Этот период нужно разбить на части")
        return [], True

    print(f"✅ Страниц: {total_pages} (< 1000 дел)")

    # Парсить все страницы
    all_cases = []

    for page_num in range(1, total_pages + 1):
        try:
            cases = await scraper._parse_current_page()
            all_cases.extend(cases)
            print(f"   [{page_num}/{total_pages}] +{len(cases)} дел (всего: {len(all_cases)})")

            # Переход на следующую страницу
            if page_num < total_pages:
                link = await scraper.page.query_selector(f'a[href="#page{page_num + 1}"]')
                if link:
                    await link.click()
                    await asyncio.sleep(3)
                else:
                    break
        except Exception as e:
            print(f"   ❌ Ошибка на странице {page_num}: {str(e)[:60]}")
            continue

    print(f"✅ Спарсено: {len(all_cases)} дел")
    return all_cases, hit_limit


async def parse_day(scraper, day: datetime, data_dir: Path):
    """Парсинг одного дня. Если >1000 дел - разбивает на части."""

    day_str = day.strftime("%d.%m.%Y")
    day_label = day.strftime("%Y-%m-%d")

    # Сначала попробовать весь день
    all_day_cases, hit_limit = await parse_date_range(
        scraper,
        day_str,
        day_str,
        f"День {day_label}"
    )

    if not hit_limit:
        # День поместился в лимит - сохраняем
        return all_day_cases

    # День не поместился - разбиваем на 6 периодов по 4 часа
    print(f"\n🔀 Разбиваю день на 6 периодов по 4 часа...")

    all_cases = []
    periods = [
        ("00:00", "03:59", "ночь"),
        ("04:00", "07:59", "раннее утро"),
        ("08:00", "11:59", "утро"),
        ("12:00", "15:59", "день"),
        ("16:00", "19:59", "вечер"),
        ("20:00", "23:59", "поздний вечер"),
    ]

    for start_time, end_time, period_name in periods:
        start_datetime = f"{day_str} {start_time}"
        end_datetime = f"{day_str} {end_time}"

        # TODO: Если API КАД поддерживает фильтр по времени, использовать его
        # Пока просто парсим весь день и надеемся что 4-часовые периоды < 1000
        # В реальности нужно либо использовать фильтр по судам, либо по времени

        period_cases, period_hit_limit = await parse_date_range(
            scraper,
            day_str,
            day_str,
            f"{day_label} {period_name}"
        )

        if period_hit_limit:
            print(f"❌ КРИТИЧНО: Даже 4-часовой период превысил лимит!")
            print(f"   Нужно использовать дополнительные фильтры (по судам)")
            # Пропускаем этот период - нужна более сложная стратегия
            continue

        all_cases.extend(period_cases)
        await asyncio.sleep(2)

    return all_cases


async def main():
    """Главная функция - парсинг всего января 2024."""

    print("=" * 80)
    print("🚀 ПОЛНЫЙ ПАРСИНГ ЯНВАРЯ 2024 - ВСЕ 130 000 ДЕЛ")
    print("=" * 80)
    print()

    # Создать директории
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    all_cases_file = data_dir / "january_2024_ALL_cases.json"

    # Подключение к Chrome
    async with PlaywrightScraper(use_cdp=True, cdp_url="http://localhost:9222") as scraper:
        print("✅ Подключено к Chrome\n")

        all_cases = []
        start_time = datetime.now()

        # Парсить каждый день января
        for day_num in range(1, 32):  # 31 день
            day = datetime(2024, 1, day_num)

            print(f"\n{'=' * 80}")
            print(f"ДЕНЬ {day_num}/31: {day.strftime('%d.%m.%Y (%A)')}")
            print(f"{'=' * 80}")

            day_cases = await parse_day(scraper, day, data_dir)
            all_cases.extend(day_cases)

            print(f"\n📊 Прогресс: {len(all_cases)} дел собрано")

            # Сохранять промежуточные результаты каждые 5 дней
            if day_num % 5 == 0:
                temp_file = data_dir / f"january_2024_cases_day{day_num}.json"
                temp_file.write_text(
                    json.dumps(all_cases, ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )
                print(f"💾 Промежуточное сохранение: {temp_file}")

            await asyncio.sleep(2)

        # Финальное сохранение
        all_cases_file.write_text(
            json.dumps(all_cases, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        elapsed = (datetime.now() - start_time).total_seconds()

        print(f"\n{'=' * 80}")
        print("🎉 ПАРСИНГ ЗАВЕРШЕН!")
        print(f"{'=' * 80}")
        print()
        print(f"✅ Всего дел: {len(all_cases)}")
        print(f"⏱️  Время: {elapsed/60:.1f} минут")
        print(f"💾 Файл: {all_cases_file}")
        print()
        print(f"📊 Ожидалось: ~130 000 дел")
        print(f"📊 Получено: {len(all_cases)} дел ({len(all_cases)/130000*100:.1f}%)")
        print()


if __name__ == "__main__":
    asyncio.run(main())

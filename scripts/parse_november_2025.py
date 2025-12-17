#!/usr/bin/env python3
"""
Парсер ноября 2025 - все дела через фильтр ДЕНЬ + СУД.
Стратегия: ДЕНЬ + СУД (только рабочие дни)
Рабочих дней: 19 (пропускаем выходные и праздники)
Запросов: 19 дней × ~100 судов = ~1900 запросов
Ожидаемый результат: ~24,000 дел

ЗАЩИТА ОТ БЛОКИРОВКИ:
- Автоматическое обнаружение блокировки (15+ судов подряд с 0 результатов)
- Автоматическая пауза 5 минут при обнаружении блокировки
- Пауза 2 минуты при явной ошибке 429
- Базовая пауза 10 секунд между судами
"""

import asyncio
import json
from pathlib import Path
from datetime import datetime, timedelta

from src.scraper.playwright_scraper import PlaywrightScraper


# Нерабочие дни в ноябре 2025
NON_WORKING_DAYS = {
    3,   # 3 ноября - перенос (мост к празднику)
    4,   # 4 ноября - День народного единства
    # Выходные (субботы и воскресенья)
    1, 2,      # сб, вс
    8, 9,      # сб, вс
    15, 16,    # сб, вс
    22, 23,    # сб, вс
    29, 30,    # сб, вс
}


def is_working_day(day_num: int) -> bool:
    """Проверить, рабочий ли день."""
    return day_num not in NON_WORKING_DAYS


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
        await asyncio.sleep(0.3)
        # Закрыть datepicker - нажать Tab для перехода к следующему полю
        await scraper.page.keyboard.press("Tab")
        await asyncio.sleep(0.5)

        # Дата ПО
        await date_inputs[1].click()
        await asyncio.sleep(0.2)
        await date_inputs[1].fill(day_str)
        await asyncio.sleep(0.3)
        # Закрыть datepicker - нажать Tab
        await scraper.page.keyboard.press("Tab")
        await asyncio.sleep(0.5)

    # Выбрать суд через input + кнопка вниз + autocomplete
    court_input = await scraper.page.query_selector('input[placeholder="название суда"]')
    if court_input:
        # Ввести название суда
        await court_input.click()
        await asyncio.sleep(0.3)
        await court_input.fill(court_name)
        await asyncio.sleep(0.3)

        # Кликнуть на кнопку вниз чтобы раскрыть список
        down_button = await scraper.page.query_selector('.js-down-button')
        if down_button:
            await down_button.click()
            await asyncio.sleep(0.7)

        # Кликнуть на первый результат в выпавшем списке
        first_option = await scraper.page.query_selector('.b-form-autocomplete-list li:first-child')
        if first_option:
            await first_option.click()
            await asyncio.sleep(0.5)
        else:
            print(f"     ⚠️  Autocomplete не появился для '{court_name[:30]}'")
            await asyncio.sleep(0.3)

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
    print("🚀 ПАРСИНГ НОЯБРЯ 2025")
    print("   Стратегия: ДЕНЬ + СУД (только рабочие дни)")
    print("   Рабочих дней: 19")
    print("   Цель: ~24,000 дел")
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

        # С какого дня начать (можно изменить для продолжения)
        START_DAY = 5  # Продолжить с 5 ноября (дни 1-4 уже обработаны или пропущены)

        # Подсчет рабочих дней
        working_days_count = sum(1 for d in range(START_DAY, 31) if is_working_day(d))

        print(f"📊 План: {working_days_count} рабочих дней × {len(courts)} судов = {working_days_count * len(courts)} запросов")
        print(f"   (Пропускаем {len([d for d in range(START_DAY, 31) if not is_working_day(d)])} выходных/праздников)\n")

        input("⏸️  Нажмите Enter чтобы начать парсинг...")
        print()

        # Загрузить существующие данные если продолжаем парсинг
        all_cases = []
        if START_DAY > 1:
            # Поискать промежуточные файлы
            last_day = START_DAY - 1
            while last_day >= 1:
                temp_file = data_dir / f"november_2025_cases_day{last_day}.json"
                if temp_file.exists():
                    print(f"📂 Загружаю существующие данные из {temp_file.name}...")
                    all_cases = json.loads(temp_file.read_text(encoding="utf-8"))
                    print(f"✅ Загружено {len(all_cases)} дел за дни 1-{last_day}\n")
                    break
                last_day -= 1

        start_time = datetime.now()

        # Счетчик для автоматического обнаружения блокировки
        consecutive_zero_results = 0
        BLOCKING_THRESHOLD = 15  # Если 15 судов подряд вернули 0 результатов - возможна блокировка
        COOLDOWN_SECONDS = 300   # 5 минут паузы при обнаружении блокировки

        # Парсить каждый день ноября 2025
        for day_num in range(START_DAY, 31):  # С START_DAY по 30 ноября
            day = datetime(2025, 11, day_num)
            day_str = day.strftime("%d.%m.%Y")

            print(f"\n{'=' * 80}")
            print(f"ДЕНЬ {day_num}/30: {day_str}")
            print(f"{'=' * 80}")

            # Пропустить нерабочие дни
            if not is_working_day(day_num):
                print(f"⏭️  ВЫХОДНОЙ - пропускаем")
                continue

            day_cases = []

            # Парсить каждый суд
            for court_idx, court_name in enumerate(courts, 1):
                print(f"[{court_idx}/{len(courts)}]", end=" ")

                try:
                    cases = await parse_day_court(scraper, day, court_name)

                    # АВТОМАТИЧЕСКОЕ ОБНАРУЖЕНИЕ БЛОКИРОВКИ
                    if len(cases) == 0:
                        consecutive_zero_results += 1
                    else:
                        consecutive_zero_results = 0  # Сброс счетчика при успешном результате

                    day_cases.extend(cases)

                    # Проверка на возможную блокировку
                    if consecutive_zero_results >= BLOCKING_THRESHOLD:
                        print(f"\n\n⚠️  ОБНАРУЖЕНА ВОЗМОЖНАЯ БЛОКИРОВКА!")
                        print(f"    {consecutive_zero_results} судов подряд вернули 0 результатов")
                        print(f"    ⏸️  Автоматическая пауза {COOLDOWN_SECONDS} секунд для снятия блокировки...")
                        print(f"    Время начала паузы: {datetime.now().strftime('%H:%M:%S')}")
                        await asyncio.sleep(COOLDOWN_SECONDS)
                        consecutive_zero_results = 0  # Сброс счетчика после паузы
                        print(f"    ▶️  Возобновление работы: {datetime.now().strftime('%H:%M:%S')}\n")

                except Exception as e:
                    error_msg = str(e)
                    print(f"     ❌ Ошибка: {error_msg[:50]}")

                    consecutive_zero_results = 0  # Сброс счетчика при ошибке

                    # Если ошибка 429 (Too Many Requests) - большая пауза
                    if "429" in error_msg or "Too Many Requests" in error_msg:
                        print(f"     ⚠️  ОШИБКА 429 - Rate Limiting!")
                        print(f"     ⏸️  Пауза 120 секунд из-за rate limiting...")
                        await asyncio.sleep(120)

                # Пауза между судами - 10 секунд чтобы не перегружать сервер
                await asyncio.sleep(10.0)

            all_cases.extend(day_cases)

            print(f"\n📊 День {day_num}: {len(day_cases)} дел | Всего: {len(all_cases)}")

            # Сохранять каждые 3 дня
            if day_num % 3 == 0:
                temp_file = data_dir / f"november_2025_cases_day{day_num}.json"
                temp_file.write_text(
                    json.dumps(all_cases, ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )
                print(f"💾 Сохранено: {temp_file}")

        # Финальное сохранение
        final_file = data_dir / "november_2025_cases.json"
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

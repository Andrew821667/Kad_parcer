#!/usr/bin/env python3
"""
Тестовый скрипт для проверки API КАД Арбитр.

Использование:
    python scripts/test_kad_api.py
"""

import asyncio
import json
from datetime import datetime

from src.scraper.kad_client import KadArbitrClient
from src.core.logging import get_logger

logger = get_logger(__name__)


async def test_search_by_case_number():
    """Тест 1: Поиск по номеру дела."""
    print("\n" + "="*60)
    print("ТЕСТ 1: Поиск дела по номеру")
    print("="*60)

    async with KadArbitrClient() as client:
        # Реальный номер дела из DevTools
        case_number = "А54-927/2025"

        print(f"\nИщем дело: {case_number}")
        print(f"Суд: Арбитражный суд Рязанской области\n")

        try:
            result = await client.search_cases(case_number=case_number)

            # Анализ результата
            total = result.get("Result", {}).get("TotalCount", 0)
            items = result.get("Result", {}).get("Items", [])

            print(f"✅ Успех! Найдено дел: {total}")

            if items:
                case = items[0]
                print(f"\nИнформация о деле:")
                print(f"  CaseId: {case.get('CaseId', 'N/A')}")
                print(f"  Номер: {case.get('CaseNumber', 'N/A')}")
                print(f"  Суд: {case.get('CourtName', 'N/A')}")
                print(f"  Судья: {case.get('Judge', 'N/A')}")
                print(f"  Дата подачи: {case.get('FilingDate', 'N/A')}")
                print(f"  Статус: {case.get('Status', 'N/A')}")
                print(f"  Категория: {case.get('Category', 'N/A')}")

                # Сохранить полный ответ для анализа
                with open("/tmp/kad_api_search_response.json", "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                print(f"\n📄 Полный ответ сохранен: /tmp/kad_api_search_response.json")
            else:
                print("⚠️ Дело не найдено")

        except Exception as e:
            print(f"❌ Ошибка: {e}")
            logger.exception("test_search_by_case_number_failed")


async def test_search_by_court_and_date():
    """Тест 2: Поиск дел АС Москвы за декабрь 2024."""
    print("\n" + "="*60)
    print("ТЕСТ 2: Поиск по суду и дате")
    print("="*60)

    async with KadArbitrClient() as client:
        court_code = "А40"  # АС Москвы
        date_from = "2024-12-01"
        date_to = "2024-12-31"

        print(f"\nПараметры поиска:")
        print(f"  Суд: {court_code} (АС г. Москвы)")
        print(f"  Период: {date_from} - {date_to}")
        print(f"  Запрос первых 10 дел\n")

        try:
            result = await client.search_by_court_and_date(
                court_code=court_code,
                date_from=date_from,
                date_to=date_to,
                count=10,
            )

            total = result.get("Result", {}).get("TotalCount", 0)
            items = result.get("Result", {}).get("Items", [])

            print(f"✅ Успех! Всего дел за период: {total}")
            print(f"Получено в ответе: {len(items)}")

            if items:
                print(f"\nПервые {min(3, len(items))} дела:")
                for i, case in enumerate(items[:3], 1):
                    print(f"\n  {i}. {case.get('CaseNumber', 'N/A')}")
                    print(f"     Категория: {case.get('Category', 'N/A')}")
                    print(f"     Дата: {case.get('FilingDate', 'N/A')}")

                # Сохранить для анализа
                with open("/tmp/kad_api_court_date_response.json", "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                print(f"\n📄 Полный ответ сохранен: /tmp/kad_api_court_date_response.json")

        except Exception as e:
            print(f"❌ Ошибка: {e}")
            logger.exception("test_search_by_court_and_date_failed")


async def test_get_case_card():
    """Тест 3: Получение карточки дела."""
    print("\n" + "="*60)
    print("ТЕСТ 3: Получение карточки дела")
    print("="*60)

    async with KadArbitrClient() as client:
        # Сначала найдем дело
        print("\nШаг 1: Поиск дела")
        search_result = await client.search_cases(case_number="А54-927/2025")

        items = search_result.get("Result", {}).get("Items", [])
        if not items:
            print("❌ Дело не найдено, пропускаем тест")
            return

        case_id = items[0].get("CaseId")
        print(f"✅ Дело найдено, CaseId: {case_id}")

        # Получаем карточку
        print("\nШаг 2: Получение HTML карточки")
        try:
            html = await client.get_case_card(case_id)

            print(f"✅ Карточка получена!")
            print(f"Размер HTML: {len(html)} байт")

            # Сохранить для анализа
            with open("/tmp/kad_case_card.html", "w", encoding="utf-8") as f:
                f.write(html)
            print(f"📄 HTML сохранен: /tmp/kad_case_card.html")

            # Базовый анализ структуры
            print("\nПредварительный анализ HTML:")
            if '<div class="case-number">' in html:
                print("  ✅ Найден: <div class='case-number'>")
            else:
                print("  ❌ НЕ найден: <div class='case-number'> (нужно искать другой селектор)")

            if '<div class="court-name">' in html:
                print("  ✅ Найден: <div class='court-name'>")
            else:
                print("  ❌ НЕ найден: <div class='court-name'>")

            if '<div class="judge">' in html:
                print("  ✅ Найден: <div class='judge'>")
            else:
                print("  ❌ НЕ найден: <div class='judge'>")

            # Поиск альтернативных паттернов
            print("\n  Поиск альтернативных паттернов...")
            if 'Судья:' in html or 'судья' in html.lower():
                print("  ℹ️ Найдено упоминание 'судья' в тексте")
            if 'Категория' in html or 'категория' in html.lower():
                print("  ℹ️ Найдено упоминание 'категория' в тексте")

        except Exception as e:
            print(f"❌ Ошибка: {e}")
            logger.exception("test_get_case_card_failed")


async def test_pagination():
    """Тест 4: Проверка пагинации."""
    print("\n" + "="*60)
    print("ТЕСТ 4: Пагинация (страница 1 и 2)")
    print("="*60)

    async with KadArbitrClient() as client:
        court_code = "А40"
        date_from = "2024-12-01"
        date_to = "2024-12-31"

        try:
            # Страница 1
            print("\nЗапрос страницы 1 (25 дел)...")
            page1 = await client.search_by_court_and_date(
                court_code=court_code,
                date_from=date_from,
                date_to=date_to,
                page=1,
                count=25,
            )

            total = page1.get("Result", {}).get("TotalCount", 0)
            items1 = page1.get("Result", {}).get("Items", [])
            print(f"✅ Страница 1: получено {len(items1)} дел из {total}")

            if len(items1) >= 25:
                # Страница 2
                print("\nЗапрос страницы 2 (25 дел)...")
                page2 = await client.search_by_court_and_date(
                    court_code=court_code,
                    date_from=date_from,
                    date_to=date_to,
                    page=2,
                    count=25,
                )

                items2 = page2.get("Result", {}).get("Items", [])
                print(f"✅ Страница 2: получено {len(items2)} дел")

                # Проверка на дубликаты
                ids1 = {item.get("CaseId") for item in items1}
                ids2 = {item.get("CaseId") for item in items2}
                overlap = ids1 & ids2

                if overlap:
                    print(f"⚠️ Найдено {len(overlap)} дубликатов между страницами!")
                else:
                    print("✅ Дубликатов между страницами нет")
            else:
                print("ℹ️ Недостаточно дел для проверки второй страницы")

        except Exception as e:
            print(f"❌ Ошибка: {e}")
            logger.exception("test_pagination_failed")


async def main():
    """Запуск всех тестов."""
    print("\n" + "█"*60)
    print("█" + " "*58 + "█")
    print("█" + "  ТЕСТИРОВАНИЕ API КАД АРБИТР".center(58) + "█")
    print("█" + " "*58 + "█")
    print("█"*60)
    print(f"\nВремя запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    tests = [
        ("Поиск по номеру дела", test_search_by_case_number),
        ("Поиск по суду и дате", test_search_by_court_and_date),
        ("Получение карточки дела", test_get_case_card),
        ("Пагинация", test_pagination),
    ]

    results = []

    for name, test_func in tests:
        try:
            await test_func()
            results.append((name, "✅ Успешно"))
        except Exception as e:
            results.append((name, f"❌ Ошибка: {e}"))
            logger.exception(f"test_failed: {name}")

    # Итоги
    print("\n" + "="*60)
    print("ИТОГИ ТЕСТИРОВАНИЯ")
    print("="*60)

    for name, result in results:
        print(f"{result:<20} {name}")

    success_count = sum(1 for _, r in results if "✅" in r)
    print(f"\nВыполнено успешно: {success_count}/{len(tests)}")

    print("\n" + "█"*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())

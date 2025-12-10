#!/usr/bin/env python3
"""
Тест API КАД Арбитр с использованием cookies из браузера

Этот скрипт использует cookies, полученные через Playwright,
для обхода HTTP 451 защиты.
"""

import asyncio
import json
import sys
from pathlib import Path

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scraper.kad_client import KadArbitrClient
from src.core.logging import get_logger

logger = get_logger(__name__)

# Путь к cookies из Playwright
COOKIES_FILE = "/tmp/kad_cookies.json"


async def test_with_cookies():
    """Тест API с использованием cookies"""
    print("\n" + "=" * 60)
    print("ТЕСТ API С COOKIES ИЗ БРАУЗЕРА")
    print("=" * 60)

    # Загружаем cookies
    print(f"\n📂 Загрузка cookies из {COOKIES_FILE}...")
    cookies = KadArbitrClient.load_cookies_from_playwright(COOKIES_FILE)

    if not cookies:
        print("❌ Cookies не найдены!")
        print("\nСначала запустите:")
        print("   python3.11 scripts/test_playwright.py")
        return False

    print(f"✅ Загружено cookies: {len(cookies)}")
    for name, value in cookies.items():
        print(f"   - {name}: {value[:20]}..." if len(value) > 20 else f"   - {name}: {value}")

    # Создаем клиент с cookies
    print("\n🔧 Создание клиента с cookies...")
    client = KadArbitrClient(cookies=cookies)

    async with client:
        # Тест 1: Поиск по номеру дела
        print("\n" + "=" * 60)
        print("ТЕСТ 1: Поиск дела А54-927/2025")
        print("=" * 60)

        try:
            result = await client.search_cases(case_number="А54-927/2025")
            print("✅ Успешно!")
            print(f"   Найдено дел: {result.get('TotalCount', 0)}")

            # Сохраняем результат
            output_path = Path("/tmp/kad_api_with_cookies_result.json")
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"💾 Результат сохранен: {output_path}")

            # Показываем первое дело
            if result.get("Result") and result["Result"].get("Items"):
                first_case = result["Result"]["Items"][0]
                print("\n📋 Первое дело:")
                print(f"   ID: {first_case.get('Id')}")
                print(f"   Номер: {first_case.get('CaseNumber')}")
                print(f"   Суд: {first_case.get('CourtName')}")
                print(f"   Тип: {first_case.get('CaseType')}")

            return True

        except Exception as e:
            print(f"❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()
            return False


async def test_bulk_search_with_cookies():
    """Тест массового поиска с cookies"""
    print("\n" + "=" * 60)
    print("ТЕСТ 2: Массовый поиск (АС Москвы, декабрь 2024)")
    print("=" * 60)

    # Загружаем cookies
    cookies = KadArbitrClient.load_cookies_from_playwright(COOKIES_FILE)

    if not cookies:
        print("❌ Cookies не найдены!")
        return False

    client = KadArbitrClient(cookies=cookies)

    async with client:
        try:
            result = await client.search_by_court_and_date(
                court_code="А40",
                date_from="2024-12-01",
                date_to="2024-12-31",
                count=10,
            )

            print("✅ Успешно!")
            print(f"   Найдено дел: {result.get('TotalCount', 0)}")

            # Сохраняем результат
            output_path = Path("/tmp/kad_api_bulk_search_result.json")
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"💾 Результат сохранен: {output_path}")

            return True

        except Exception as e:
            print(f"❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()
            return False


async def main():
    """Главная функция"""
    print("\n" + "█" * 60)
    print("█" + " " * 58 + "█")
    print("█" + "   ТЕСТ API КАД С COOKIES".center(58) + "█")
    print("█" + " " * 58 + "█")
    print("█" * 60)

    # Проверяем наличие cookies
    if not Path(COOKIES_FILE).exists():
        print("\n❌ Файл cookies не найден!")
        print(f"   Ожидается: {COOKIES_FILE}")
        print("\n💡 Сначала запустите:")
        print("   python3.11 scripts/test_playwright.py")
        print("\n   Это создаст файл с cookies.")
        return

    # Тест 1: Простой поиск
    success1 = await test_with_cookies()

    if success1:
        # Тест 2: Массовый поиск
        success2 = await test_bulk_search_with_cookies()
    else:
        success2 = False

    # Итоги
    print("\n" + "=" * 60)
    print("ИТОГИ")
    print("=" * 60)
    print(f"Тест 1 (поиск по номеру): {'✅ Успешно' if success1 else '❌ Ошибка'}")
    print(f"Тест 2 (массовый поиск):  {'✅ Успешно' if success2 else '❌ Ошибка'}")

    if success1 and success2:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОШЛИ!")
        print("\n📊 Результаты в /tmp/:")
        print("   - kad_api_with_cookies_result.json")
        print("   - kad_api_bulk_search_result.json")
    elif success1:
        print("\n⚠️ Частично работает (только простой поиск)")
    else:
        print("\n❌ API по-прежнему не работает даже с cookies")
        print("\n💡 Возможные причины:")
        print("   1. Cookies устарели (повторите Playwright тест)")
        print("   2. Нужны дополнительные заголовки")
        print("   3. API требует JavaScript выполнения")

    print("\n" + "█" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""
Debug script to see what's happening in the browser.
Run with visible browser to debug form filling.
"""

import asyncio

from src.scraper.playwright_scraper import PlaywrightScraper


async def main():
    """Run debug parsing with visible browser."""
    print("🔍 Открываю браузер (видимый режим)...")
    print("Будете видеть что происходит на сайте kad.arbitr.ru\n")

    # Запускаем браузер в видимом режиме
    async with PlaywrightScraper(headless=False, base_delay=(5.0, 8.0)) as scraper:
        print("Тест 1: Поиск по суду А40-КС за январь 2024")
        print("=" * 60)

        try:
            results = await scraper.search_by_court_and_date(
                court_code="А40-КС",
                date_from="01.01.2024",
                date_to="31.01.2024",
            )

            print(f"\n✅ Результат: найдено {len(results)} дел")

            if results:
                print("\nПервые 3 дела:")
                for i, case in enumerate(results[:3], 1):
                    print(f"\n{i}. {case.get('case_number', 'N/A')}")
                    print(f"   Суд: {case.get('court', 'N/A')}")
                    print(f"   URL: {case.get('url', 'N/A')}")
            else:
                print("\n⚠️  Дела не найдены!")
                print("\nВозможные причины:")
                print("1. Код суда 'А40-КС' неверный")
                print("2. Селекторы формы изменились")
                print("3. За этот период действительно нет дел")

        except Exception as e:
            print(f"\n❌ Ошибка: {e}")
            import traceback

            traceback.print_exc()

        print("\n" + "=" * 60)
        print("Тест 2: Поиск по известному делу А40-1/24")
        print("=" * 60)

        try:
            results = await scraper.search_by_court_and_date(
                court_code="",  # Без фильтра по суду
                date_from="01.01.2024",
                date_to="31.12.2024",
                case_number="А40-1/24",
            )

            print(f"\n✅ Результат: найдено {len(results)} дел")

            if results:
                print("\nНайденное дело:")
                case = results[0]
                print(f"Номер: {case.get('case_number', 'N/A')}")
                print(f"Суд: {case.get('court', 'N/A')}")
                print(f"Истец: {case.get('plaintiff', 'N/A')}")
                print(f"URL: {case.get('url', 'N/A')}")
            else:
                print("\n⚠️  Дело А40-1/24 не найдено!")

        except Exception as e:
            print(f"\n❌ Ошибка: {e}")

        input("\n\nНажмите Enter чтобы закрыть браузер...")


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""
Анализ результатов парсинга и расчет таймлайна для полной базы.

Анализирует:
- Структуру документов
- Категории споров
- Связи между актами
- Статистику по судам и судьям

Рассчитывает:
- Время парсинга всей базы (2020-2025)
- Объем данных
- Требования к ресурсам
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter
from typing import Dict, List, Any


def load_results() -> Dict[str, Any]:
    """Загрузить результаты парсинга."""
    data_dir = Path("data")

    # Загрузить дела
    cases_file = data_dir / "january_2024_cases.json"
    if not cases_file.exists():
        print("❌ Файл january_2024_cases.json не найден!")
        print("   Запустите сначала: python scripts/parse_all_january_2024.py")
        exit(1)

    cases = json.loads(cases_file.read_text(encoding="utf-8"))

    # Загрузить метаданные PDF
    pdf_metadata_file = data_dir / "january_2024_pdf_metadata.json"
    pdf_metadata = []
    if pdf_metadata_file.exists():
        pdf_metadata = json.loads(pdf_metadata_file.read_text(encoding="utf-8"))

    # Загрузить статистику
    stats_file = data_dir / "january_2024_stats.json"
    stats = {}
    if stats_file.exists():
        stats = json.loads(stats_file.read_text(encoding="utf-8"))

    return {
        "cases": cases,
        "pdf_metadata": pdf_metadata,
        "stats": stats,
    }


def analyze_case_categories(cases: List[Dict]) -> Dict[str, int]:
    """Анализ категорий дел."""
    categories = Counter()

    for case in cases:
        # Категория может быть в case_type или нужно извлечь из других полей
        category = case.get("case_type", "Unknown")
        categories[category] += 1

    return dict(categories)


def analyze_courts(cases: List[Dict]) -> Dict[str, Any]:
    """Анализ распределения по судам."""
    courts = Counter()
    court_details = {}

    for case in cases:
        court = case.get("court", "Unknown")
        courts[court] += 1

        if court not in court_details:
            court_details[court] = {
                "count": 0,
                "case_numbers": [],
            }

        court_details[court]["count"] += 1
        court_details[court]["case_numbers"].append(case.get("case_number"))

    return {
        "total_courts": len(courts),
        "distribution": dict(courts.most_common(20)),
        "details": court_details,
    }


def analyze_judges(cases: List[Dict]) -> Dict[str, Any]:
    """Анализ распределения по судьям."""
    judges = Counter()

    for case in cases:
        judge = case.get("judge", "Unknown")
        if judge and judge != "Unknown":
            judges[judge] += 1

    return {
        "total_judges": len(judges),
        "distribution": dict(judges.most_common(20)),
        "avg_cases_per_judge": sum(judges.values()) / len(judges) if judges else 0,
    }


def analyze_pdf_documents(pdf_metadata: List[Dict]) -> Dict[str, Any]:
    """Анализ скачанных PDF документов."""
    if not pdf_metadata:
        return {}

    total_size = sum(doc["pdf_size"] for doc in pdf_metadata)
    doc_titles = Counter()

    for doc in pdf_metadata:
        title = doc.get("document_title", "Unknown")
        # Извлечь тип документа из названия
        if "Решение" in title or "решение" in title:
            doc_type = "Решение"
        elif "Определение" in title or "определение" in title:
            doc_type = "Определение"
        elif "Постановление" in title or "постановление" in title:
            doc_type = "Постановление"
        else:
            doc_type = "Другое"

        doc_titles[doc_type] += 1

    return {
        "total_pdfs": len(pdf_metadata),
        "total_size_mb": total_size / (1024 * 1024),
        "avg_size_kb": (total_size / len(pdf_metadata)) / 1024 if pdf_metadata else 0,
        "document_types": dict(doc_titles),
    }


def calculate_timeline(stats: Dict[str, Any], total_cases: int) -> Dict[str, Any]:
    """Рассчитать таймлайн парсинга всей базы."""

    parsing_stats = stats.get("parsing", {})
    avg_time_per_page = parsing_stats.get("avg_time_per_page", 5.0)  # секунды

    # Оценки объема данных

    # 1 месяц = ~1000 дел (40 страниц)
    cases_per_month = total_cases

    # Период: 2020-2025 = 6 лет = 72 месяца
    months_total = 72
    estimated_total_cases = cases_per_month * months_total

    # 21 апелляционный суд
    courts_total = 21
    estimated_cases_all_courts = estimated_total_cases * courts_total

    # Расчет времени

    # Среднее время на 1 страницу (с учетом задержек)
    time_per_page_sec = avg_time_per_page + 2  # добавляем запас

    # 1 месяц = 40 страниц
    pages_per_month = 40
    time_per_month_min = (time_per_page_sec * pages_per_month) / 60

    # Все месяцы одного суда
    time_per_court_hours = (time_per_month_min * months_total) / 60

    # Все суды (последовательно)
    time_all_courts_days = (time_per_court_hours * courts_total) / 24

    # Все суды (параллельно, 5 потоков)
    parallel_workers = 5
    time_all_courts_parallel_days = time_all_courts_days / parallel_workers

    return {
        "estimates": {
            "cases_per_month": cases_per_month,
            "total_months": months_total,
            "total_courts": courts_total,
            "estimated_total_cases_one_court": estimated_total_cases,
            "estimated_total_cases_all_courts": estimated_cases_all_courts,
        },
        "timing": {
            "avg_time_per_page_sec": time_per_page_sec,
            "time_per_month_min": time_per_month_min,
            "time_per_court_hours": time_per_court_hours,
            "time_all_courts_sequential_days": time_all_courts_days,
            "time_all_courts_parallel_days": time_all_courts_parallel_days,
        },
        "storage": {
            "avg_pdf_size_kb": 250,  # средний размер PDF
            "estimated_pdfs_per_case": 2,  # в среднем 2 документа на дело
            "estimated_total_pdfs": estimated_cases_all_courts * 2,
            "estimated_storage_gb": (estimated_cases_all_courts * 2 * 250) / (1024 * 1024),
        },
        "recommendations": {
            "parallel_workers": parallel_workers,
            "batch_size": 10,  # страниц за раз
            "checkpoint_frequency": "каждые 100 страниц",
            "estimated_timeline": f"{time_all_courts_parallel_days:.0f} дней ({time_all_courts_parallel_days/30:.1f} месяцев)",
        }
    }


def print_analysis_report(data: Dict[str, Any]):
    """Вывести отчет анализа."""

    cases = data["cases"]
    pdf_metadata = data["pdf_metadata"]
    stats = data["stats"]

    print("=" * 80)
    print("📊 АНАЛИЗ РЕЗУЛЬТАТОВ ПАРСИНГА")
    print("=" * 80)
    print()

    # 1. Общая статистика
    print("1️⃣  ОБЩАЯ СТАТИСТИКА")
    print("-" * 80)
    print(f"   Всего дел: {len(cases)}")
    print(f"   PDF скачано: {len(pdf_metadata)}")
    print(f"   Время парсинга: {stats.get('parsing', {}).get('parsing_time_sec', 0):.1f} сек")
    print()

    # 2. Категории дел
    print("2️⃣  КАТЕГОРИИ ДЕЛ")
    print("-" * 80)
    categories = analyze_case_categories(cases)
    for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"   {cat}: {count}")
    print()

    # 3. Распределение по судам
    print("3️⃣  РАСПРЕДЕЛЕНИЕ ПО СУДАМ")
    print("-" * 80)
    courts_analysis = analyze_courts(cases)
    print(f"   Всего судов: {courts_analysis['total_courts']}")
    for court, count in list(courts_analysis['distribution'].items())[:5]:
        print(f"   {court}: {count}")
    print()

    # 4. Судьи
    print("4️⃣  СУДЬИ")
    print("-" * 80)
    judges_analysis = analyze_judges(cases)
    print(f"   Всего судей: {judges_analysis['total_judges']}")
    print(f"   Среднее дел на судью: {judges_analysis['avg_cases_per_judge']:.1f}")
    for judge, count in list(judges_analysis['distribution'].items())[:5]:
        print(f"   {judge}: {count}")
    print()

    # 5. PDF документы
    print("5️⃣  PDF ДОКУМЕНТЫ")
    print("-" * 80)
    pdf_analysis = analyze_pdf_documents(pdf_metadata)
    if pdf_analysis:
        print(f"   Всего PDF: {pdf_analysis['total_pdfs']}")
        print(f"   Общий размер: {pdf_analysis['total_size_mb']:.1f} MB")
        print(f"   Средний размер: {pdf_analysis['avg_size_kb']:.1f} KB")
        print()
        print("   Типы документов:")
        for doc_type, count in pdf_analysis['document_types'].items():
            print(f"      {doc_type}: {count}")
    print()

    # 6. Расчет таймлайна
    print("6️⃣  РАСЧЕТ ТАЙМЛАЙНА ДЛЯ ПОЛНОЙ БАЗЫ")
    print("-" * 80)
    timeline = calculate_timeline(stats, len(cases))

    print("   📅 Оценки объема:")
    print(f"      • Дел в месяц (1 суд): {timeline['estimates']['cases_per_month']}")
    print(f"      • Всего месяцев (2020-2025): {timeline['estimates']['total_months']}")
    print(f"      • Всего судов: {timeline['estimates']['total_courts']}")
    print(f"      • Всего дел (1 суд, 6 лет): {timeline['estimates']['estimated_total_cases_one_court']:,}")
    print(f"      • Всего дел (21 суд, 6 лет): {timeline['estimates']['estimated_total_cases_all_courts']:,}")
    print()

    print("   ⏱️  Расчет времени:")
    print(f"      • Время на 1 страницу: {timeline['timing']['avg_time_per_page_sec']:.1f} сек")
    print(f"      • Время на 1 месяц: {timeline['timing']['time_per_month_min']:.1f} мин")
    print(f"      • Время на 1 суд (6 лет): {timeline['timing']['time_per_court_hours']:.1f} часов")
    print(f"      • Время на все (последовательно): {timeline['timing']['time_all_courts_sequential_days']:.0f} дней")
    print(f"      • Время на все (5 потоков): {timeline['timing']['time_all_courts_parallel_days']:.0f} дней")
    print()

    print("   💾 Оценка хранилища:")
    print(f"      • Средний размер PDF: {timeline['storage']['avg_pdf_size_kb']} KB")
    print(f"      • PDF на дело: {timeline['storage']['estimated_pdfs_per_case']}")
    print(f"      • Всего PDF: {timeline['storage']['estimated_total_pdfs']:,}")
    print(f"      • Требуется места: {timeline['storage']['estimated_storage_gb']:.1f} GB")
    print()

    print("   🎯 РЕКОМЕНДАЦИИ:")
    print(f"      • Параллельных потоков: {timeline['recommendations']['parallel_workers']}")
    print(f"      • Размер батча: {timeline['recommendations']['batch_size']} страниц")
    print(f"      • Частота чекпоинтов: {timeline['recommendations']['checkpoint_frequency']}")
    print(f"      • ⏰ ИТОГОВЫЙ ТАЙМЛАЙН: {timeline['recommendations']['estimated_timeline']}")
    print()

    print("=" * 80)
    print("✅ АНАЛИЗ ЗАВЕРШЕН")
    print("=" * 80)
    print()

    # Сохранить полный анализ
    analysis_file = Path("data/january_2024_analysis.json")
    analysis_file.write_text(
        json.dumps({
            "categories": categories,
            "courts": courts_analysis,
            "judges": judges_analysis,
            "pdfs": pdf_analysis,
            "timeline": timeline,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"💾 Полный анализ сохранен: {analysis_file}")


if __name__ == "__main__":
    print("🔍 Загрузка результатов парсинга...")
    print()

    data = load_results()
    print_analysis_report(data)

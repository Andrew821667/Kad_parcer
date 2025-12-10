"""
Mapping of court codes to their full names as they appear on kad.arbitr.ru website.
"""

# Московский округ - 18 судов
MOSCOW_DISTRICT_COURTS = {
    # Кассация
    "А40-КС": "АС Московского округа",

    # Апелляция
    "А40-АП": "Девятый арбитражный апелляционный суд",

    # Первая инстанция
    "А40": "АС города Москвы",
    "А41": "АС Московской области",
    "А54": "АС Рязанской области",
    "А56": "АС города Санкт-Петербурга и Ленинградской области",
    "А13": "АС Вологодской области",
    "А05": "АС Архангельской области",
    "А66": "АС Тверской области",
    "А21": "АС Калининградской области",
    "А26": "АС Республики Карелия",
    "А42": "АС Мурманской области",
    "А44": "АС Новгородской области",
    "А52": "АС Псковской области",
    "А14": "АС Воронежской области",
    "А36": "АС Липецкой области",
    "А08": "АС Белгородской области",
    "А64": "АС Тамбовской области",
}


def get_court_full_name(court_code: str) -> str:
    """
    Get full court name by code.

    Args:
        court_code: Court code (e.g., 'А40', 'А40-КС')

    Returns:
        Full court name as it appears on kad.arbitr.ru

    Raises:
        ValueError: If court code not found
    """
    full_name = MOSCOW_DISTRICT_COURTS.get(court_code)
    if not full_name:
        raise ValueError(
            f"Unknown court code: {court_code}. "
            f"Available codes: {', '.join(MOSCOW_DISTRICT_COURTS.keys())}"
        )
    return full_name

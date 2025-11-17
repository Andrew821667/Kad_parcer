# KAD Parser

Система парсинга документов из системы арбитражных судов РФ (КАД Арбитр).

## Возможности

- 🔍 **Парсинг дел** - Сбор информации о делах из КАД Арбитр
- 📄 **Обработка документов** - Парсинг PDF, DOCX и HTML документов
- 💾 **Хранение данных** - PostgreSQL для структурированных данных, MinIO для файлов
- 🚀 **Асинхронная обработка** - Celery для фоновых задач
- 🌐 **REST API** - FastAPI для доступа к данным
- 🎯 **Rate Limiting** - Контроль частоты запросов

## Технологический стек

- **Backend**: Python 3.11+, FastAPI, SQLAlchemy 2.0
- **Database**: PostgreSQL 15+
- **Cache/Queue**: Redis
- **Storage**: MinIO (S3-compatible)
- **Tasks**: Celery
- **Parsing**: BeautifulSoup4, pdfplumber, python-docx
- **HTTP**: httpx (async)

## Структура проекта

```
kad_parser/
├── src/
│   ├── core/           # Конфигурация, логирование, исключения
│   ├── scraper/        # Скрейпинг КАД Арбитр
│   ├── parser/         # Парсинг документов (HTML/PDF/DOCX)
│   ├── storage/        # База данных и файловое хранилище
│   ├── tasks/          # Celery задачи
│   ├── api/            # FastAPI приложение
│   ├── web/            # Web UI (опционально)
│   └── cli/            # CLI интерфейс
├── tests/              # Тесты
├── docker/             # Docker конфигурация
└── scripts/            # Утилиты
```

## Быстрый старт

### Установка

```bash
# Установка зависимостей с uv
uv pip install -e ".[dev]"

# Или с pip
pip install -e ".[dev]"
```

### Настройка

Скопируйте `.env.example` в `.env` и настройте переменные окружения:

```bash
cp .env.example .env
```

### Запуск с Docker

```bash
# Запуск всех сервисов
docker-compose -f docker/docker-compose.yml up -d

# API доступен на http://localhost:8000
# MinIO UI на http://localhost:9001
```

### Запуск локально

```bash
# API сервер
kad-parser serve

# Или напрямую
uvicorn src.api.app:app --reload

# Celery worker
celery -A src.tasks.celery_app worker --loglevel=info
```

## Использование

### CLI

```bash
# Версия
kad-parser version

# Парсинг дела
kad-parser scrape А40-123456/2024

# Запуск API
kad-parser serve --host 0.0.0.0 --port 8000
```

### API

```bash
# Проверка здоровья
curl http://localhost:8000/health

# Список доступных endpoints
curl http://localhost:8000/docs
```

### Python API

```python
from src.scraper.kad_client import KadArbitrClient

async with KadArbitrClient() as client:
    # Поиск дел
    result = await client.search_cases(
        case_number="А40-123456/2024"
    )

    # Получение карточки дела
    html = await client.get_case_card("case-id")

    # Скачивание документа
    content = await client.download_document("/doc/url")
```

## Разработка

### Тесты

```bash
# Все тесты
pytest

# С покрытием
pytest --cov=src --cov-report=html

# Конкретный модуль
pytest tests/unit/test_scraper_kad_client.py -v
```

### Линтинг

```bash
# Ruff
ruff check src/
ruff format src/

# MyPy
mypy src/
```

### Миграции БД

```bash
# Создать миграцию
alembic revision --autogenerate -m "Description"

# Применить миграции
alembic upgrade head

# Откат
alembic downgrade -1
```

## Архитектура

### Модули

- **scraper** - Работа с КАД Арбитр API, rate limiting, retry логика
- **parser** - Извлечение данных из HTML, PDF, DOCX документов
- **storage** - Repository pattern для БД, MinIO для файлов
- **tasks** - Celery задачи для асинхронной обработки
- **api** - REST API с FastAPI
- **cli** - Command-line интерфейс

### База данных

Основные модели:
- `Case` - Арбитражное дело
- `Participant` - Участник дела
- `Document` - Судебный документ
- `Hearing` - Судебное заседание
- `ScrapingTask` - История задач парсинга

## Лицензия

MIT License - см. [LICENSE](LICENSE)

## Автор

Andrew821667

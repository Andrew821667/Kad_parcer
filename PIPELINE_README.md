# Интеграционный Pipeline КАД Парсер

Полный автоматизированный pipeline для обработки дел арбитражных судов РФ.

## Архитектура Pipeline

```
JSON метаданные → SQL БД → Скачивание PDF → Конвертация MD → Очистка PDF
      ↓              ↓            ↓              ↓              ↓
  Парсер      Дедупликация   Rate limit    Batch процесс  Экономия места
```

## Возможности

✅ **Checkpoint система** - возобновление с любого места
✅ **Обработка ошибок** - продолжение при сбоях
✅ **Детальное логирование** - в файл и консоль
✅ **Статистика в реальном времени** - прогресс и метрики
✅ **Rate limiting** - безопасная работа с КАД Арбитр
✅ **Batch обработка** - параллельная конвертация PDF

## Требования

1. **Chrome с CDP** (Chrome DevTools Protocol):
   ```bash
   google-chrome --remote-debugging-port=9222
   ```

2. **Python зависимости**:
   ```bash
   pip install playwright pdfplumber aiohttp
   playwright install chromium
   ```

3. **Готовый JSON с метаданными** - используйте существующий парсер

## Использование

### Базовый запуск

```bash
# Обработать месяц с готовым JSON
python scripts/process_cases.py \
  --month 2025-11 \
  --db data/kad_2025.db \
  --json data/november_2025_cases.json
```

### Возобновление из checkpoint

```bash
# Продолжить с места остановки
python scripts/process_cases.py \
  --resume checkpoint_2025-11.json
```

### Кастомизация директорий

```bash
python scripts/process_cases.py \
  --month 2025-11 \
  --db data/kad_2025.db \
  --json data/november_2025_cases.json \
  --download-dir /tmp/pdfs \
  --documents-dir /mnt/storage/documents
```

### CDP на другом порту

```bash
python scripts/process_cases.py \
  --month 2025-11 \
  --db data/kad_2025.db \
  --json data/november_2025_cases.json \
  --cdp-url http://localhost:9333
```

## Формат JSON метаданных

Pipeline ожидает JSON массив с объектами дел:

```json
[
  {
    "case_number": "А40-12345-2024",
    "court": "Арбитражный суд города Москвы",
    "registration_date": "2024-01-15",
    "status": "Рассмотрение дела завершено",
    "parties": "ООО Рога и Копыта против ООО Васюки"
  },
  ...
]
```

Используйте `scripts/parse_january_by_day_and_court.py` или другой парсер для создания JSON.

## Структура checkpoint файла

Checkpoint автоматически создается как `checkpoint_YYYY-MM.json`:

```json
{
  "stage": "downloading_converting",
  "month": "2025-11",
  "db_path": "data/kad_2025.db",
  "processed_cases": ["А40-12345-2024", "А40-67890-2024"],
  "failed_cases": [
    {
      "case_number": "А40-11111-2024",
      "error": "Navigation failed",
      "timestamp": "2024-12-12T10:30:00"
    }
  ],
  "stats": {
    "total_cases": 40000,
    "imported_cases": 39500,
    "downloaded_documents": 120000,
    "converted_documents": 119800,
    "failed_downloads": 200,
    "failed_conversions": 50
  },
  "started_at": "2024-12-12T08:00:00",
  "updated_at": "2024-12-12T10:30:00"
}
```

## Этапы Pipeline

### ЭТАП 1: Парсинг метаданных

- Загружает JSON файл с метаданными дел
- Альтернатива: используйте готовый парсер для создания JSON

### ЭТАП 2: Импорт в SQL

- Импортирует метаданные в SQLite базу
- Автоматическая дедупликация (`INSERT OR IGNORE`)
- Создает индексы для быстрого поиска

### ЭТАП 3: Скачивание и конвертация

Для каждого дела:

1. **Навигация** - открывает страницу дела на КАД Арбитр
2. **Извлечение** - получает список документов из "Электронное дело"
3. **Фильтрация** - оставляет только важные типы:
   - Решение (первая инстанция)
   - Постановление (апелляция/кассация)
   - Определение Верховного Суда
   - Завершающие определения
4. **Скачивание** - загружает PDF с retry (3 попытки)
5. **Конвертация** - преобразует PDF → Markdown (batch, 4 воркера)
6. **Обновление БД** - записывает пути к MD файлам
7. **Очистка** - удаляет PDF для экономии места

## Результаты

### Структура файлов

```
Kad_parcer/
├── data/
│   └── kad_2025.db                    # SQL метаданные
├── documents/                          # MD документы
│   └── 2025/
│       ├── А40-12345-2025/
│       │   ├── Решение_первая_инстанция.md
│       │   ├── Постановление_апелляция.md
│       │   └── Постановление_кассация.md
│       └── А40-67890-2025/
│           └── Решение.md
├── checkpoint_2025-11.json             # Checkpoint
└── pipeline.log                        # Лог выполнения
```

### Финальный отчет

Pipeline выводит детальный отчет:

```
================================================================================
ФИНАЛЬНЫЙ ОТЧЕТ
================================================================================
Месяц: 2025-11
База данных: data/kad_2025.db

Всего дел: 40000
Импортировано в БД: 39500
Обработано дел: 38900
Провалено дел: 600

Скачано документов: 120000
Конвертировано в MD: 119800
Провалено скачиваний: 200
Провалено конвертаций: 50

Время выполнения: 5 days, 3:24:15
================================================================================
```

## Обработка ошибок

### Ошибки скачивания

- Автоматический retry (3 попытки с паузой 2 сек)
- Пропуск проблемных документов
- Запись в `failed_cases` в checkpoint

### Ошибки конвертации

- Пропуск поврежденных PDF
- Запись в статистику
- Продолжение с следующим документом

### Прерывание процесса

При `Ctrl+C` или сбое:

1. Checkpoint сохраняется автоматически
2. Выводится финальный отчет
3. Можно продолжить с `--resume`

## Rate Limiting

Pipeline соблюдает лимиты КАД Арбитр:

- **5 секунд** между запросами документов
- **2 секунды** между делами
- **60 секунд** пауза при ошибке 429

## Производительность

### Метрики на ноябрь 2025 (~40k дел)

- **Дела:** ~40,000
- **Документы:** ~160,000 (4 на дело в среднем)
- **MD файлы:** ~8 GB
- **Время:** 3-5 дней (с учетом rate limiting)

### Скорость обработки

- **Скачивание:** 1 дело каждые 7 сек (rate limit)
- **Конвертация:** 5024 PDF/мин (batch процесс)
- **Всего:** ~11,500 дел/день

## Рекомендации

### Для больших объемов

```bash
# Используйте отдельный диск для documents
--documents-dir /mnt/storage/documents

# Используйте tmpfs для downloads (RAM)
--download-dir /dev/shm/pdfs
```

### Для надежности

```bash
# Запуск в screen/tmux
screen -S pipeline
python scripts/process_cases.py --month 2025-11 --db data/kad_2025.db --json data/nov.json
# Ctrl+A+D для detach
```

### Мониторинг

```bash
# Следить за логом
tail -f pipeline.log

# Проверить checkpoint
cat checkpoint_2025-11.json | jq '.stats'
```

## Troubleshooting

### Chrome не подключается

```bash
# Проверить, что Chrome запущен с CDP
ps aux | grep chrome | grep remote-debugging-port

# Перезапустить Chrome
pkill chrome
google-chrome --remote-debugging-port=9222 &
```

### Ошибка "Database is locked"

```bash
# Закрыть другие процессы, использующие БД
lsof data/kad_2025.db

# Или используйте WAL mode (включен автоматически)
```

### Нехватка места на диске

```bash
# Использовать tmpfs для временных PDF
--download-dir /dev/shm/pdfs

# Или настроить автоматическую очистку (включена по умолчанию)
```

## Примеры использования

### Полный цикл для ноября 2025

```bash
# 1. Парсинг метаданных (отдельно)
python scripts/parse_january_by_day_and_court.py \
  --month 2025-11 \
  --output data/november_2025_cases.json

# 2. Запуск pipeline
python scripts/process_cases.py \
  --month 2025-11 \
  --db data/kad_2025.db \
  --json data/november_2025_cases.json
```

### Тестирование на небольшой выборке

```bash
# Создать тестовый JSON с 10 делами
head -n 10 data/november_2025_cases.json > data/test_cases.json

# Запустить на тесте
python scripts/process_cases.py \
  --month 2025-11-test \
  --db data/test.db \
  --json data/test_cases.json
```

### Возобновление после сбоя

```bash
# Pipeline прервался на середине
# Просто возобновляем из checkpoint

python scripts/process_cases.py \
  --resume checkpoint_2025-11.json

# Все уже обработанные дела будут пропущены автоматически
```

## Интеграция с модулями

Pipeline использует все созданные модули:

```python
from src.database import SQLiteManager          # ЭТАП 1
from src.converter import batch_convert         # ЭТАП 2
from src.downloader import DocumentDownloader   # ЭТАП 3
```

## Следующие шаги

После успешного выполнения pipeline:

1. **Анализ данных** - используйте SQL запросы к БД
2. **Full-text search** - используйте ripgrep по MD файлам
3. **Экспорт** - создайте отчеты и аналитику
4. **Масштабирование** - запустите на весь 2025 год

## Поддержка

Логи сохраняются в:
- `pipeline.log` - полный лог выполнения
- `checkpoint_*.json` - прогресс и статистика

Для отладки используйте уровень DEBUG:

```python
# В scripts/process_cases.py изменить
logging.basicConfig(level=logging.DEBUG, ...)
```

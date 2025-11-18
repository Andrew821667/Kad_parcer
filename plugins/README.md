# Плагины KAD Parser

Эта директория содержит плагины для расширения функциональности KAD Parser.

## Типы плагинов

### 1. Плагины парсеров
Пользовательские парсеры документов для дополнительных форматов файлов.

**Пример:**
```python
from src.plugins.base import ParserPlugin

class MyParserPlugin(ParserPlugin):
    @property
    def name(self) -> str:
        return "my_parser"

    async def parse(self, content: bytes, content_type: str) -> dict:
        # Парсинг содержимого документа
        return {"text": "распарсенный контент"}

    def supports_content_type(self, content_type: str) -> bool:
        return content_type == "application/my-format"
```

### 2. Плагины процессоров
Процессоры данных, которые преобразуют или обогащают данные.

**Пример:**
```python
from src.plugins.base import ProcessorPlugin, PluginHook

class MyProcessorPlugin(ProcessorPlugin):
    def get_hooks(self) -> list[PluginHook]:
        return [PluginHook.AFTER_SCRAPE]

    async def process(self, data: dict) -> dict:
        # Обработка данных
        data["enriched"] = True
        return data
```

### 3. Плагины экспортеров
Пользовательские форматы экспорта.

**Пример:**
```python
from src.plugins.base import ExporterPlugin

class MyExporterPlugin(ExporterPlugin):
    async def export(self, data: list[dict], options: dict) -> bytes:
        # Экспорт в пользовательский формат
        return b"exported data"

    def get_file_extension(self) -> str:
        return ".myformat"
```

## Хуки плагинов

Плагины могут подписываться на различные хуки в жизненном цикле приложения:

### Обработка документов
- `BEFORE_PARSE`: Перед парсингом документа
- `AFTER_PARSE`: После успешного парсинга документа
- `PARSE_FAILED`: Когда парсинг документа не удался

### Обработка дел
- `BEFORE_SCRAPE`: Перед парсингом дела
- `AFTER_SCRAPE`: После успешного парсинга дела
- `SCRAPE_FAILED`: Когда парсинг дела не удался

### Обработка данных
- `BEFORE_SAVE`: Перед сохранением данных в БД
- `AFTER_SAVE`: После сохранения данных в БД

### Экспорт
- `BEFORE_EXPORT`: Перед экспортом данных
- `AFTER_EXPORT`: После экспорта данных

## Загрузка плагинов

Плагины автоматически загружаются из этой директории при запуске приложения.

Для перезагрузки плагинов без перезапуска приложения:

```bash
POST /api/plugins/reload
```

## Конфигурация плагина

Настройка плагина через API:

```bash
POST /api/plugins/{имя_плагина}/configure
{
  "config": {
    "option1": "value1",
    "option2": "value2"
  }
}
```

## Включение/отключение плагинов

```bash
# Включить плагин
PATCH /api/plugins/{имя_плагина}/status
{
  "enabled": true
}

# Отключить плагин
PATCH /api/plugins/{имя_плагина}/status
{
  "enabled": false
}
```

## Примеры плагинов

См. `example_exporter.py` и `example_processor.py` для полных рабочих примеров.

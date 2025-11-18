# KAD Parser Plugins

This directory contains plugins for extending the KAD Parser functionality.

## Plugin Types

### 1. Parser Plugins
Custom document parsers for additional file formats.

**Example:**
```python
from src.plugins.base import ParserPlugin

class MyParserPlugin(ParserPlugin):
    @property
    def name(self) -> str:
        return "my_parser"

    async def parse(self, content: bytes, content_type: str) -> dict:
        # Parse document content
        return {"text": "parsed content"}

    def supports_content_type(self, content_type: str) -> bool:
        return content_type == "application/my-format"
```

### 2. Processor Plugins
Data processors that transform or enrich data.

**Example:**
```python
from src.plugins.base import ProcessorPlugin, PluginHook

class MyProcessorPlugin(ProcessorPlugin):
    def get_hooks(self) -> list[PluginHook]:
        return [PluginHook.AFTER_SCRAPE]

    async def process(self, data: dict) -> dict:
        # Process data
        data["enriched"] = True
        return data
```

### 3. Exporter Plugins
Custom export formats.

**Example:**
```python
from src.plugins.base import ExporterPlugin

class MyExporterPlugin(ExporterPlugin):
    async def export(self, data: list[dict], options: dict) -> bytes:
        # Export to custom format
        return b"exported data"

    def get_file_extension(self) -> str:
        return ".myformat"
```

## Plugin Hooks

Plugins can subscribe to various hooks in the application lifecycle:

### Document Processing
- `BEFORE_PARSE`: Before parsing a document
- `AFTER_PARSE`: After successfully parsing a document
- `PARSE_FAILED`: When document parsing fails

### Case Processing
- `BEFORE_SCRAPE`: Before scraping a case
- `AFTER_SCRAPE`: After successfully scraping a case
- `SCRAPE_FAILED`: When case scraping fails

### Data Processing
- `BEFORE_SAVE`: Before saving data to database
- `AFTER_SAVE`: After saving data to database

### Export
- `BEFORE_EXPORT`: Before exporting data
- `AFTER_EXPORT`: After exporting data

## Loading Plugins

Plugins are automatically loaded from this directory when the application starts.

To reload plugins without restarting the application:

```bash
POST /api/plugins/reload
```

## Plugin Configuration

Configure a plugin via API:

```bash
POST /api/plugins/{plugin_name}/configure
{
  "config": {
    "option1": "value1",
    "option2": "value2"
  }
}
```

## Enable/Disable Plugins

```bash
# Enable plugin
PATCH /api/plugins/{plugin_name}/status
{
  "enabled": true
}

# Disable plugin
PATCH /api/plugins/{plugin_name}/status
{
  "enabled": false
}
```

## Example Plugins

See `example_exporter.py` and `example_processor.py` for complete working examples.

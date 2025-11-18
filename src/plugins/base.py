"""Base classes for plugin system."""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Optional


class PluginType(str, Enum):
    """Plugin types."""

    PARSER = "parser"  # Custom document parsers
    PROCESSOR = "processor"  # Data processors
    ANALYZER = "analyzer"  # Data analyzers
    EXPORTER = "exporter"  # Export formats
    NOTIFIER = "notifier"  # Notification channels
    SCRAPER = "scraper"  # Custom scrapers


class PluginHook(str, Enum):
    """Plugin hook points."""

    # Document processing hooks
    BEFORE_PARSE = "before_parse"
    AFTER_PARSE = "after_parse"
    PARSE_FAILED = "parse_failed"

    # Case processing hooks
    BEFORE_SCRAPE = "before_scrape"
    AFTER_SCRAPE = "after_scrape"
    SCRAPE_FAILED = "scrape_failed"

    # Data processing hooks
    BEFORE_SAVE = "before_save"
    AFTER_SAVE = "after_save"

    # Export hooks
    BEFORE_EXPORT = "before_export"
    AFTER_EXPORT = "after_export"


class Plugin(ABC):
    """Base plugin class."""

    def __init__(self) -> None:
        """Initialize plugin."""
        self._enabled = True
        self._config: dict[str, Any] = {}

    @property
    @abstractmethod
    def name(self) -> str:
        """Plugin name."""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """Plugin version."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Plugin description."""
        pass

    @property
    @abstractmethod
    def plugin_type(self) -> PluginType:
        """Plugin type."""
        pass

    @property
    def author(self) -> Optional[str]:
        """Plugin author."""
        return None

    @property
    def enabled(self) -> bool:
        """Check if plugin is enabled."""
        return self._enabled

    def enable(self) -> None:
        """Enable plugin."""
        self._enabled = True

    def disable(self) -> None:
        """Disable plugin."""
        self._enabled = False

    def configure(self, config: dict[str, Any]) -> None:
        """Configure plugin.

        Args:
            config: Configuration dictionary
        """
        self._config = config

    def get_config(self, key: str, default: Any = None) -> Any:
        """Get configuration value.

        Args:
            key: Configuration key
            default: Default value

        Returns:
            Configuration value
        """
        return self._config.get(key, default)

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize plugin (async).

        This method is called when the plugin is loaded.
        Use it to set up any resources needed by the plugin.
        """
        pass

    @abstractmethod
    async def cleanup(self) -> None:
        """Cleanup plugin resources (async).

        This method is called when the plugin is unloaded.
        Use it to clean up any resources used by the plugin.
        """
        pass

    def get_hooks(self) -> list[PluginHook]:
        """Get list of hooks this plugin subscribes to.

        Returns:
            List of plugin hooks
        """
        return []

    async def on_hook(self, hook: PluginHook, context: dict[str, Any]) -> dict[str, Any]:
        """Handle hook event.

        Args:
            hook: Hook type
            context: Hook context data

        Returns:
            Modified context data
        """
        return context


class ParserPlugin(Plugin):
    """Base class for parser plugins."""

    @property
    def plugin_type(self) -> PluginType:
        """Plugin type."""
        return PluginType.PARSER

    @abstractmethod
    async def parse(self, content: bytes, content_type: str) -> dict[str, Any]:
        """Parse document content.

        Args:
            content: Document content bytes
            content_type: Content MIME type

        Returns:
            Parsed data dictionary
        """
        pass

    @abstractmethod
    def supports_content_type(self, content_type: str) -> bool:
        """Check if this parser supports the given content type.

        Args:
            content_type: Content MIME type

        Returns:
            True if supported, False otherwise
        """
        pass


class ProcessorPlugin(Plugin):
    """Base class for processor plugins."""

    @property
    def plugin_type(self) -> PluginType:
        """Plugin type."""
        return PluginType.PROCESSOR

    @abstractmethod
    async def process(self, data: dict[str, Any]) -> dict[str, Any]:
        """Process data.

        Args:
            data: Input data

        Returns:
            Processed data
        """
        pass


class ExporterPlugin(Plugin):
    """Base class for exporter plugins."""

    @property
    def plugin_type(self) -> PluginType:
        """Plugin type."""
        return PluginType.EXPORTER

    @abstractmethod
    async def export(self, data: list[dict[str, Any]], format_options: dict[str, Any]) -> bytes:
        """Export data to specific format.

        Args:
            data: Data to export
            format_options: Format-specific options

        Returns:
            Exported data as bytes
        """
        pass

    @abstractmethod
    def get_file_extension(self) -> str:
        """Get file extension for this export format.

        Returns:
            File extension (e.g., '.json', '.xml')
        """
        pass

    @abstractmethod
    def get_mime_type(self) -> str:
        """Get MIME type for this export format.

        Returns:
            MIME type (e.g., 'application/json')
        """
        pass

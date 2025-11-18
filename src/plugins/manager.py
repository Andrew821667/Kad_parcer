"""Plugin manager for loading and managing plugins."""

import importlib.util
import inspect
from pathlib import Path
from typing import Any, Optional

from src.core.logging import get_logger
from src.plugins.base import Plugin, PluginHook, PluginType

logger = get_logger(__name__)


class PluginManager:
    """Manages plugin loading, initialization, and execution."""

    def __init__(self, plugins_dir: Optional[Path] = None) -> None:
        """Initialize plugin manager.

        Args:
            plugins_dir: Directory containing plugin modules
        """
        self.plugins_dir = plugins_dir or Path("plugins")
        self._plugins: dict[str, Plugin] = {}
        self._hooks: dict[PluginHook, list[Plugin]] = {hook: [] for hook in PluginHook}

    async def load_plugins(self) -> None:
        """Load all plugins from plugins directory."""
        if not self.plugins_dir.exists():
            logger.warning("plugins_directory_not_found", path=str(self.plugins_dir))
            self.plugins_dir.mkdir(parents=True, exist_ok=True)
            return

        logger.info("loading_plugins", path=str(self.plugins_dir))

        # Load all Python files from plugins directory
        for plugin_path in self.plugins_dir.glob("*.py"):
            if plugin_path.name.startswith("_"):
                continue

            try:
                await self._load_plugin_from_file(plugin_path)
            except Exception as e:
                logger.error(
                    "plugin_load_failed",
                    path=str(plugin_path),
                    error=str(e),
                    exc_info=True,
                )

        logger.info("plugins_loaded", count=len(self._plugins))

    async def _load_plugin_from_file(self, plugin_path: Path) -> None:
        """Load plugin from file.

        Args:
            plugin_path: Path to plugin file
        """
        # Load module
        spec = importlib.util.spec_from_file_location(plugin_path.stem, plugin_path)
        if not spec or not spec.loader:
            raise ValueError(f"Could not load plugin from {plugin_path}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Find Plugin classes in module
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, Plugin) and obj is not Plugin and not inspect.isabstract(obj):
                # Instantiate plugin
                plugin = obj()

                # Initialize plugin
                await plugin.initialize()

                # Register plugin
                self._plugins[plugin.name] = plugin

                # Register hooks
                for hook in plugin.get_hooks():
                    self._hooks[hook].append(plugin)

                logger.info(
                    "plugin_loaded",
                    name=plugin.name,
                    version=plugin.version,
                    type=plugin.plugin_type.value,
                    hooks=len(plugin.get_hooks()),
                )

    def get_plugin(self, name: str) -> Optional[Plugin]:
        """Get plugin by name.

        Args:
            name: Plugin name

        Returns:
            Plugin instance or None
        """
        return self._plugins.get(name)

    def get_plugins_by_type(self, plugin_type: PluginType) -> list[Plugin]:
        """Get all plugins of a specific type.

        Args:
            plugin_type: Plugin type

        Returns:
            List of plugins
        """
        return [p for p in self._plugins.values() if p.plugin_type == plugin_type and p.enabled]

    def list_plugins(self) -> list[dict[str, Any]]:
        """List all loaded plugins.

        Returns:
            List of plugin info dictionaries
        """
        return [
            {
                "name": p.name,
                "version": p.version,
                "description": p.description,
                "type": p.plugin_type.value,
                "author": p.author,
                "enabled": p.enabled,
                "hooks": [h.value for h in p.get_hooks()],
            }
            for p in self._plugins.values()
        ]

    async def execute_hook(self, hook: PluginHook, context: dict[str, Any]) -> dict[str, Any]:
        """Execute all plugins subscribed to a hook.

        Args:
            hook: Hook type
            context: Hook context data

        Returns:
            Modified context data
        """
        plugins = self._hooks.get(hook, [])

        for plugin in plugins:
            if not plugin.enabled:
                continue

            try:
                context = await plugin.on_hook(hook, context)
            except Exception as e:
                logger.error(
                    "plugin_hook_error",
                    plugin=plugin.name,
                    hook=hook.value,
                    error=str(e),
                    exc_info=True,
                )

        return context

    async def enable_plugin(self, name: str) -> bool:
        """Enable plugin.

        Args:
            name: Plugin name

        Returns:
            True if successful, False otherwise
        """
        plugin = self.get_plugin(name)
        if plugin:
            plugin.enable()
            logger.info("plugin_enabled", name=name)
            return True
        return False

    async def disable_plugin(self, name: str) -> bool:
        """Disable plugin.

        Args:
            name: Plugin name

        Returns:
            True if successful, False otherwise
        """
        plugin = self.get_plugin(name)
        if plugin:
            plugin.disable()
            logger.info("plugin_disabled", name=name)
            return True
        return False

    async def configure_plugin(self, name: str, config: dict[str, Any]) -> bool:
        """Configure plugin.

        Args:
            name: Plugin name
            config: Configuration dictionary

        Returns:
            True if successful, False otherwise
        """
        plugin = self.get_plugin(name)
        if plugin:
            plugin.configure(config)
            logger.info("plugin_configured", name=name, config=config)
            return True
        return False

    async def unload_all(self) -> None:
        """Unload all plugins."""
        logger.info("unloading_plugins", count=len(self._plugins))

        for plugin in self._plugins.values():
            try:
                await plugin.cleanup()
            except Exception as e:
                logger.error(
                    "plugin_cleanup_error",
                    plugin=plugin.name,
                    error=str(e),
                    exc_info=True,
                )

        self._plugins.clear()
        self._hooks = {hook: [] for hook in PluginHook}

        logger.info("plugins_unloaded")


# Global plugin manager instance
_plugin_manager: Optional[PluginManager] = None


def get_plugin_manager() -> PluginManager:
    """Get global plugin manager instance.

    Returns:
        PluginManager instance
    """
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
    return _plugin_manager

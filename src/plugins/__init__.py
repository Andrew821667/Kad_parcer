"""Plugin system for extensibility."""

from src.plugins.base import Plugin, PluginHook, PluginType
from src.plugins.manager import PluginManager

__all__ = ["Plugin", "PluginHook", "PluginType", "PluginManager"]

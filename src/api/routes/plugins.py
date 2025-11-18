"""Plugin management routes."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel

from src.api.dependencies import get_current_active_user
from src.core.logging import get_logger
from src.plugins.manager import get_plugin_manager
from src.storage.database.auth_models import User

logger = get_logger(__name__)
router = APIRouter(prefix="/plugins", tags=["plugins"])


class PluginConfig(BaseModel):
    """Plugin configuration request."""

    config: dict[str, Any]


class PluginStatusUpdate(BaseModel):
    """Plugin status update request."""

    enabled: bool


@router.get("", response_model=list[dict])
async def list_plugins(
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """List all loaded plugins."""
    manager = get_plugin_manager()
    plugins = manager.list_plugins()
    return plugins


@router.get("/{plugin_name}", response_model=dict)
async def get_plugin(
    plugin_name: str,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Get plugin details."""
    manager = get_plugin_manager()
    plugin = manager.get_plugin(plugin_name)

    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin not found")

    return {
        "name": plugin.name,
        "version": plugin.version,
        "description": plugin.description,
        "type": plugin.plugin_type.value,
        "author": plugin.author,
        "enabled": plugin.enabled,
        "hooks": [h.value for h in plugin.get_hooks()],
    }


@router.patch("/{plugin_name}/status", response_model=dict)
async def update_plugin_status(
    plugin_name: str,
    status_update: PluginStatusUpdate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Enable or disable plugin."""
    manager = get_plugin_manager()

    if status_update.enabled:
        success = await manager.enable_plugin(plugin_name)
    else:
        success = await manager.disable_plugin(plugin_name)

    if not success:
        raise HTTPException(status_code=404, detail="Plugin not found")

    logger.info(
        "plugin_status_updated",
        plugin=plugin_name,
        enabled=status_update.enabled,
        user_id=current_user.id,
    )

    return {"message": "Plugin status updated", "enabled": status_update.enabled}


@router.post("/{plugin_name}/configure", response_model=dict)
async def configure_plugin(
    plugin_name: str,
    config: PluginConfig,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Configure plugin."""
    manager = get_plugin_manager()
    success = await manager.configure_plugin(plugin_name, config.config)

    if not success:
        raise HTTPException(status_code=404, detail="Plugin not found")

    logger.info(
        "plugin_configured",
        plugin=plugin_name,
        user_id=current_user.id,
    )

    return {"message": "Plugin configured successfully"}


@router.post("/reload", status_code=202)
async def reload_plugins(
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Reload all plugins from plugins directory."""
    manager = get_plugin_manager()

    # Unload existing plugins
    await manager.unload_all()

    # Reload plugins
    await manager.load_plugins()

    plugins_count = len(manager.list_plugins())

    logger.info(
        "plugins_reloaded",
        count=plugins_count,
        user_id=current_user.id,
    )

    return {"message": "Plugins reloaded successfully", "count": plugins_count}


@router.get("/types", response_model=list[str])
async def list_plugin_types() -> Any:
    """List available plugin types."""
    from src.plugins.base import PluginType

    return [t.value for t in PluginType]


@router.get("/hooks", response_model=list[str])
async def list_plugin_hooks() -> Any:
    """List available plugin hooks."""
    from src.plugins.base import PluginHook

    return [h.value for h in PluginHook]

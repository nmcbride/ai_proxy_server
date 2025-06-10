"""
Plugin Registry System

This module provides a decorator-based plugin registration system that allows
plugins to auto-register themselves when their modules are imported.
"""

import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Global plugin registry
_plugin_registry: Dict[str, List[Dict[str, Any]]] = {
    "before_request": [],
    "after_request": [],
}


def register_plugin(
    name: str,
    endpoints: Optional[List[str]] = None,
    priority: int = 50,
    hook: str = "before_request",
    description: str = "",
    version: str = "1.0.0",
) -> Callable:
    """
    Decorator to register a plugin function.

    Args:
        name: Unique name for the plugin
        endpoints: List of endpoint patterns this plugin applies to (* for all)
        priority: Execution priority (lower numbers run first)
        hook: Which hook to register for ('before_request' or 'after_request')
        description: Optional description of what the plugin does
        version: Plugin version
    """
    if endpoints is None:
        endpoints = ["*"]

    def decorator(func: Callable) -> Callable:
        plugin_info = {
            "name": name,
            "function": func,
            "endpoints": endpoints,
            "priority": priority,
            "description": description,
            "version": version,
            "hook": hook,
        }

        # Validate hook type
        if hook not in _plugin_registry:
            raise ValueError(
                f"Invalid hook '{hook}'. Must be one of: {list(_plugin_registry.keys())}"
            )

        # Check for duplicate names within the same hook
        existing_names = [p["name"] for p in _plugin_registry[hook]]
        if name in existing_names:
            logger.warning(
                f"Plugin '{name}' is already registered for hook '{hook}'. Overriding."
            )
            # Remove existing plugin with same name
            _plugin_registry[hook] = [
                p for p in _plugin_registry[hook] if p["name"] != name
            ]

        # Register the plugin
        _plugin_registry[hook].append(plugin_info)
        logger.info(
            f"Registered plugin '{name}' for hook '{hook}' with priority {priority}"
        )

        return func

    return decorator


def get_plugins(hook: str) -> List[Dict[str, Any]]:
    """Get all registered plugins for a specific hook, sorted by priority."""
    if hook not in _plugin_registry:
        return []

    # Sort by priority (lower numbers first), then by name for consistency
    return sorted(_plugin_registry[hook], key=lambda x: (x["priority"], x["name"]))


def get_all_plugins() -> Dict[str, List[Dict[str, Any]]]:
    """Get all registered plugins organized by hook."""
    return {hook: get_plugins(hook) for hook in _plugin_registry.keys()}


def clear_registry() -> None:
    """Clear all registered plugins. Useful for testing."""
    for hook in _plugin_registry:
        _plugin_registry[hook].clear()
    logger.info("Plugin registry cleared")


def get_plugin_info(name: str, hook: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Get information about a specific plugin."""
    if hook:
        hooks_to_search = [hook]
    else:
        hooks_to_search = list(_plugin_registry.keys())

    for h in hooks_to_search:
        for plugin in _plugin_registry[h]:
            if plugin["name"] == name:
                return plugin

    return None


def list_plugin_names() -> Dict[str, List[str]]:
    """Get a list of all registered plugin names organized by hook."""
    return {
        hook: [p["name"] for p in plugins] for hook, plugins in _plugin_registry.items()
    }

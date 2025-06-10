"""
Plugin Manager

Handles loading and executing plugins from both system and user folders
using the registry system for auto-registration.
"""

import fnmatch
import glob
import importlib.util
import logging
import os
import sys
from typing import Any, Dict, List

import yaml

from .registry import get_all_plugins, get_plugins, list_plugin_names

logger = logging.getLogger(__name__)


class PluginManager:
    """
    Manages plugin loading and execution using the registry system.

    Loads plugins from two locations:
    - app/plugins/ (system plugins that ship with the application)
    - plugins/ (user-created plugins)

    Loads configuration from configs/plugins.yaml
    """

    def __init__(self) -> None:
        self.loaded_modules: List[str] = []
        self.system_plugins_dir = "app/plugins"
        self.user_plugins_dir = "plugins"
        self.config_path = "configs/plugins.yaml"
        self.plugin_configs: Dict[str, Any] = {}

    def load_plugins(self) -> Dict[str, int]:
        """
        Load plugin configuration and all plugins from both system and user directories.

        Returns:
            Dict with counts of loaded plugins by type
        """
        # Load plugin configuration first
        self._load_plugin_config()

        counts = {"system": 0, "user": 0, "total": 0}

        # Load system plugins first (lower default priority)
        logger.info("Loading system plugins...")
        system_count = self._load_plugins_from_directory(
            self.system_plugins_dir, plugin_type="system"
        )
        counts["system"] = system_count

        # Load user plugins second (can override system plugins with same names)
        logger.info("Loading user plugins...")
        user_count = self._load_plugins_from_directory(
            self.user_plugins_dir, plugin_type="user"
        )
        counts["user"] = user_count

        counts["total"] = system_count + user_count

        # Log summary
        registry_counts = list_plugin_names()
        logger.info("Plugin loading complete:")
        logger.info(f"  System plugins loaded: {system_count}")
        logger.info(f"  User plugins loaded: {user_count}")
        logger.info(f"  Total files loaded: {counts['total']}")
        logger.info(
            f"  Registered before_request plugins: {len(registry_counts.get('before_request', []))}"
        )
        logger.info(
            f"  Registered after_request plugins: {len(registry_counts.get('after_request', []))}"
        )

        return counts

    def _load_plugin_config(self) -> None:
        """Load plugin configuration from YAML file."""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r") as f:
                    config_data = yaml.safe_load(f) or {}

                self.plugin_configs = config_data.get("plugins", {})
                logger.info(f"Loaded plugin configuration from {self.config_path}")
                logger.info(f"  Configured plugins: {list(self.plugin_configs.keys())}")
            else:
                logger.warning(f"Plugin config file not found: {self.config_path}")
                self.plugin_configs = {}
        except Exception as e:
            logger.error(f"Failed to load plugin configuration: {e}")
            self.plugin_configs = {}

    def _get_plugin_config(self, plugin_name: str) -> Dict[str, Any]:
        """Get configuration for a specific plugin."""
        plugin_config = self.plugin_configs.get(plugin_name, {})

        # Check if plugin is enabled (default to True if not specified)
        enabled = plugin_config.get("enabled", True)
        if not enabled:
            return {"enabled": False}

        # Return the plugin's config section, ensuring it's a dict
        config_section = plugin_config.get("config", {})
        if not isinstance(config_section, dict):
            logger.warning(f"Invalid config format for plugin {plugin_name}, using empty dict")
            return {}

        return config_section

    def _load_plugins_from_directory(self, directory: str, plugin_type: str) -> int:
        """Load all Python files from a directory as plugins."""
        if not os.path.exists(directory):
            logger.warning(f"Plugin directory not found: {directory}")
            return 0

        loaded_count = 0
        python_files = glob.glob(os.path.join(directory, "*.py"))

        for filepath in python_files:
            filename = os.path.basename(filepath)

            # Skip __init__.py and files starting with underscore
            if filename.startswith("__") or filename.startswith("_"):
                continue

            try:
                module_name = f"{plugin_type}_plugin_{filename[:-3]}"

                # Load the module - this triggers plugin registration via decorators
                spec = importlib.util.spec_from_file_location(module_name, filepath)
                if spec is None or spec.loader is None:
                    logger.error(f"Could not load spec for {filepath}")
                    continue

                module = importlib.util.module_from_spec(spec)

                # Add to sys.modules so imports work properly
                sys.modules[module_name] = module

                # Execute the module - this is where @register_plugin decorators run
                spec.loader.exec_module(module)

                self.loaded_modules.append(module_name)
                loaded_count += 1

                logger.info(f"Loaded {plugin_type} plugin: {filename}")

            except Exception as e:
                logger.error(f"Failed to load {plugin_type} plugin {filename}: {e}")
                continue

        return loaded_count

    def execute_before_request_plugins(
        self, request_data: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute all registered before_request plugins.

        Args:
            request_data: The request data (kept clean)
            context: Plugin context with metadata (endpoint, request_id, etc.)

        Returns:
            Modified request data
        """
        return self._execute_plugins("before_request", request_data, context)

    def execute_after_request_plugins(
        self, response_data: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute all registered after_request plugins.

        Args:
            response_data: The response data (kept clean)
            context: Plugin context with metadata (endpoint, request_id, etc.)

        Returns:
            Modified response data
        """
        return self._execute_plugins("after_request", response_data, context)

    def _execute_plugins(
        self, hook: str, data: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute plugins for a specific hook with context."""
        plugins = get_plugins(hook)

        if not plugins:
            return data

        # Extract endpoint from context
        endpoint = context.get("endpoint", "")

        executed_count = 0
        for plugin in plugins:
            try:
                # Check if plugin applies to this endpoint
                if self._endpoint_matches(endpoint, plugin["endpoints"]):
                    # Get plugin-specific configuration
                    plugin_config = self._get_plugin_config(plugin["name"])

                    # Check if plugin is enabled
                    if plugin_config.get("enabled", True) is False:
                        logger.debug(f"Skipping disabled plugin: {plugin['name']}")
                        continue

                    # Add plugin config to context
                    plugin_context = context.copy()
                    plugin_context["config"] = plugin_config

                    logger.debug(f"Executing {hook} plugin: {plugin['name']}")
                    data = plugin["function"](data, plugin_context)
                    executed_count += 1
                else:
                    logger.debug(
                        f"Skipping {hook} plugin {plugin['name']} (endpoint mismatch)"
                    )
            except Exception as e:
                logger.error(f"Error in {hook} plugin {plugin['name']}: {e}")
                # Continue with other plugins even if one fails
                continue

        if executed_count > 0:
            logger.debug(f"Executed {executed_count} {hook} plugins")

        return data

    def _endpoint_matches(self, endpoint: str, patterns: List[str]) -> bool:
        """Check if an endpoint matches any of the given patterns."""
        if not patterns:
            return True

        for pattern in patterns:
            if pattern == "*":
                return True
            if fnmatch.fnmatch(endpoint, pattern):
                return True
            if endpoint == pattern:
                return True

        return False

    def get_plugin_status(self) -> Dict[str, Any]:
        """Get status information about loaded plugins."""
        all_plugins = get_all_plugins()

        status: Dict[str, Any] = {
            "loaded_modules": len(self.loaded_modules),
            "config_file": self.config_path,
            "configured_plugins": list(self.plugin_configs.keys()),
            "registered_plugins": {
                hook: len(plugins) for hook, plugins in all_plugins.items()
            },
            "plugins_by_hook": {},
        }

        for hook, plugins in all_plugins.items():
            status["plugins_by_hook"][hook] = [
                {
                    "name": p["name"],
                    "priority": p["priority"],
                    "endpoints": p["endpoints"],
                    "description": p["description"],
                    "version": p["version"],
                    "config_available": p["name"] in self.plugin_configs,
                    "enabled": self._get_plugin_config(p["name"]).get("enabled", True)
                    is not False,
                }
                for p in plugins
            ]

        return status


# Global plugin manager instance
plugin_manager = PluginManager()

"""
Simple MCP Server Configuration
"""

import os
from pathlib import Path
from typing import Any, Dict

import structlog
import yaml

logger = structlog.get_logger()


class MCPConfig:
    """Simple MCP server configuration manager"""

    def __init__(self, config_path: Path | None = None):
        self.config_path = config_path or Path("config/mcp_servers.yaml")
        self.servers: Dict[str, Dict[str, Any]] = {}

    def load_config(self) -> Dict[str, Dict[str, Any]]:
        """Load MCP server configurations"""
        # Start with empty config
        self.servers = {}

        # Load from file if it exists
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    config_data = yaml.safe_load(f) or {}
                    self.servers.update(config_data.get("mcp_servers", {}))
                logger.info(
                    "MCP config loaded from file",
                    path=str(self.config_path),
                    servers=len(self.servers),
                )
            except Exception as e:
                logger.error(
                    "Failed to load MCP config",
                    path=str(self.config_path),
                    error=str(e),
                )

        # Override with environment variables
        self._load_from_environment()

        return self.servers

    def _load_from_environment(self) -> None:
        """Load MCP server configs from environment variables"""
        # Look for MCP_SERVER_* environment variables
        for key, value in os.environ.items():
            if key.startswith("MCP_SERVER_"):
                server_name = key[11:].lower()  # Remove MCP_SERVER_ prefix
                try:
                    # Expect JSON format for full config
                    import json

                    server_config = json.loads(value)
                    self.servers[server_name] = server_config
                    logger.info("MCP server config loaded from env", server=server_name)
                except json.JSONDecodeError:
                    # Simple command format: MCP_SERVER_WEATHER=python weather_server.py
                    parts = value.split()
                    if parts:
                        self.servers[server_name] = {
                            "transport": "stdio",
                            "command": parts[0],
                            "args": parts[1:] if len(parts) > 1 else [],
                        }
                        logger.info(
                            "MCP server config loaded from env (simple)",
                            server=server_name,
                        )

    def create_example_config(self) -> bool:
        """Create an example MCP configuration file"""
        example_config = {
            "mcp_servers": {
                # Weather server example
                "weather": {
                    "transport": "stdio",
                    "command": "python",
                    "args": ["path/to/weather_server.py"],
                },
                # Database server example
                "database": {
                    "transport": "stdio",
                    "command": "mcp-sqlite-server",
                    "args": ["--db-path", "data/app.db"],
                },
                # HTTP server example
                "external_api": {
                    "transport": "http",
                    "server_url": "http://localhost:8080/mcp",
                    "auth": {"type": "bearer", "token": "your_token_here"},
                },
                # Home Assistant example
                "home_assistant": {
                    "transport": "stdio",
                    "command": "mcp-homeassistant",
                    "args": [
                        "--url",
                        "http://localhost:8123",
                        "--token",
                        "your_ha_token",
                    ],
                    "env": {
                        "HA_URL": "http://localhost:8123",
                        "HA_TOKEN": "your_home_assistant_token",
                    },
                },
                # File system server example
                "filesystem": {
                    "transport": "stdio",
                    "command": "mcp-filesystem-server",
                    "args": ["--root", "/safe/directory"],
                },
            }
        }

        try:
            # Ensure config directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self.config_path, "w", encoding="utf-8") as f:
                yaml.dump(example_config, f, default_flow_style=False, indent=2)

            logger.info("Example MCP config created", path=str(self.config_path))
            return True

        except Exception as e:
            logger.error(
                "Failed to create example MCP config",
                path=str(self.config_path),
                error=str(e),
            )
            return False

    def get_servers(self) -> Dict[str, Dict[str, Any]]:
        """Get all configured servers"""
        return self.servers.copy()

    def add_server(self, name: str, config: Dict[str, Any]) -> None:
        """Add a new server configuration"""
        self.servers[name] = config
        logger.info("MCP server added", server=name)

    def remove_server(self, name: str) -> bool:
        """Remove a server configuration"""
        if name in self.servers:
            del self.servers[name]
            logger.info("MCP server removed", server=name)
            return True
        return False

    def save_config(self) -> bool:
        """Save current configuration to file"""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            config_data = {"mcp_servers": self.servers}

            with open(self.config_path, "w", encoding="utf-8") as f:
                yaml.dump(config_data, f, default_flow_style=False, indent=2)

            logger.info("MCP config saved", path=str(self.config_path))
            return True

        except Exception as e:
            logger.error(
                "Failed to save MCP config", path=str(self.config_path), error=str(e)
            )
            return False


# Global config instance
mcp_config = MCPConfig()

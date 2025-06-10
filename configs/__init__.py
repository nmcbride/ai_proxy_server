"""
Configuration package for AI Proxy Server

This package contains all configuration files:
- config.py: Python pydantic settings
- mcp_servers.yaml: MCP server configurations  
- plugins.yaml: Plugin configurations
"""

from .config import settings

__all__ = ["settings"] 
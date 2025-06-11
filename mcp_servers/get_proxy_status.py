#!/usr/bin/env python3
"""
Proxy Status MCP Server
Provides status information about the AI Proxy Server including plugins, MCP tools, and configuration.
"""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List

import httpx
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server

# Proxy Status MCP server
server = Server("proxy-status-server")

# Configuration for the proxy server
PROXY_BASE_URL = "http://localhost:8000"


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available proxy status tools."""
    return [
        types.Tool(
            name="get_proxy_status",
            description="Get comprehensive status information about the AI Proxy Server. This tool returns markdown content that MUST be displayed exactly as returned with all line breaks preserved. Do not summarize, reformat, or add any commentary. Simply output the tool response directly with proper markdown formatting intact.",
            inputSchema={
                "type": "object",
                "properties": {
                    "include_debug": {
                        "type": "boolean",
                        "description": "Include detailed debug information",
                        "default": False
                    }
                },
                "required": []
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any] | None) -> list[types.TextContent]:
    """Handle tool calls."""
    
    if name == "get_proxy_status":
        include_debug = arguments.get("include_debug", False) if arguments else False
        
        try:
            status_info = await get_comprehensive_proxy_status(include_debug)
            return [
                types.TextContent(
                    type="text",
                    text=status_info
                )
            ]
        except Exception as e:
            error_message = f"""# ❌ Proxy Status Error

**Error**: Failed to retrieve proxy status information

**Details**: {str(e)}

**Timestamp**: {datetime.now().isoformat()}

**Suggestion**: Ensure the AI Proxy Server is running on {PROXY_BASE_URL}
"""
            return [
                types.TextContent(
                    type="text",
                    text=error_message
                )
            ]
    

        except Exception as e:
            error_message = f"""# ❌ Proxy Status Error

**Error**: Failed to retrieve proxy status information

**Details**: {str(e)}

**Timestamp**: {datetime.now().isoformat()}

**Suggestion**: Ensure the AI Proxy Server is running on {PROXY_BASE_URL}
"""
            return [
                types.TextContent(
                    type="text",
                    text=error_message
                )
            ]
    else:
        return [
            types.TextContent(
                type="text",
                text=f"# ❌ Unknown Tool\n\n**Error**: Unknown tool '{name}'"
            )
        ]


async def get_comprehensive_proxy_status(include_debug: bool = False) -> str:
    """Get comprehensive status information about the proxy server."""
    
    async with httpx.AsyncClient(timeout=3.0) as client:
        # Gather information from various endpoints
        config_data = await fetch_endpoint(client, "/config")
        mcp_status = await fetch_endpoint(client, "/mcp/status")
        debug_mcp_status = await fetch_endpoint(client, "/debug/mcp/status")
        
        # Get current timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        # Build markdown status report
        markdown_report = f"""# AI Proxy Server Status Report

**Generated**: {timestamp}  
**Server**: {PROXY_BASE_URL}

---

## Server Configuration

| Setting | Value |
|---------|-------|
"""
        
        # Dynamically add all configuration values
        if config_data and not config_data.get('error'):
            for key, value in sorted(config_data.items()):
                # Format the key to be more readable
                formatted_key = key.replace('_', ' ').title()
                # Handle different value types
                if isinstance(value, bool):
                    formatted_value = f"`{value}`"
                elif isinstance(value, (int, float)) and 'TIMEOUT' in key.upper():
                    formatted_value = f"`{value}s`"
                elif isinstance(value, str) and len(value) > 100:
                    formatted_value = f"`{value[:100]}...`"
                else:
                    formatted_value = f"`{value}`"
                markdown_report += f"| **{formatted_key}** | {formatted_value} |\n"
        else:
            markdown_report += "| **Status** | `Configuration unavailable` |\n"
        
        markdown_report += "\n"

        # MCP Servers Section
        servers = debug_mcp_status.get('servers', {})
        markdown_report += f"""---

## MCP Servers Status

**Total Connected Servers**: {len(servers)}

"""

        if servers:
            for server_name, server_info in servers.items():
                status_text = "Connected" if server_info.get('connected') else "Disconnected"
                markdown_report += f"""### {server_name}
- **Status**: {status_text}
- **Transport**: {server_info.get('transport', 'Unknown')}
- **Tools**: {server_info.get('tools', 0)}
- **Resources**: {server_info.get('resources', 0)}
- **Prompts**: {server_info.get('prompts', 0)}

"""
        else:
            markdown_report += "**No MCP servers configured**\n\n"

        # Available Tools Section
        tools = debug_mcp_status.get('tools', [])
        markdown_report += f"""---

## Available MCP Tools

**Total Tools**: {len(tools)}

"""

        if tools:
            # Group tools by server
            tools_by_server = {}
            for tool in tools:
                server_name = tool.get('server', 'Unknown')
                if server_name not in tools_by_server:
                    tools_by_server[server_name] = []
                tools_by_server[server_name].append(tool)
            
            for server_name, server_tools in tools_by_server.items():
                markdown_report += f"""### {server_name} Tools ({len(server_tools)})

| Tool | Description |
|------|-------------|
"""
                for tool in server_tools:
                    name = tool.get('name', 'Unknown')
                    description = tool.get('description', 'No description')
                    # Clean up description for table
                    clean_desc = description.replace('\n', ' ').replace('|', '\\|')[:100]
                    if len(description) > 100:
                        clean_desc += "..."
                    markdown_report += f"| `{name}` | {clean_desc} |\n"
                markdown_report += "\n"
        else:
            markdown_report += "**No tools available**\n\n"

        # Tool Registry Section
        tool_registry = debug_mcp_status.get('tool_registry', {})
        if tool_registry and include_debug:
            markdown_report += f"""---

## Tool Registry (Debug)

**Total Registered Tools**: {len(tool_registry)}

| Tool Name | Server |
|-----------|--------|
"""
            for tool_name, server_name in tool_registry.items():
                markdown_report += f"| `{tool_name}` | {server_name} |\n"
            markdown_report += "\n"

        # Resources and Prompts (if any)
        resources = debug_mcp_status.get('resources', [])
        prompts = debug_mcp_status.get('prompts', [])
        
        if resources or prompts:
            markdown_report += f"""---

## Additional MCP Capabilities

"""
            if resources:
                markdown_report += f"**Resources**: {len(resources)} available\n"
            if prompts:
                markdown_report += f"**Prompts**: {len(prompts)} available\n"
            markdown_report += "\n"

        # Health Check Summary
        total_tools = len(tools)
        connected_servers = len([s for s in servers.values() if s.get('connected')])
        
        markdown_report += f"""---

## Health Summary

| Metric | Status |
|--------|--------|
| **Server Health** | {'Healthy' if config_data and not config_data.get('error') else 'Unhealthy'} |
| **MCP Integration** | {'Active' if connected_servers > 0 else 'Inactive'} |
| **Connected Servers** | {connected_servers}/{len(servers)} |
| **Available Tools** | {total_tools} |
| **Hybrid Streaming** | {'Enabled' if config_data.get('ENABLE_HYBRID_STREAMING') else 'Disabled'} |

---

*Generated by Proxy Status MCP Server*
"""

        return markdown_report


async def fetch_endpoint(client: httpx.AsyncClient, endpoint: str) -> Dict[str, Any]:
    """Fetch data from a proxy endpoint."""
    try:
        response = await client.get(f"{PROXY_BASE_URL}{endpoint}")
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}


async def main():
    """Run the proxy status MCP server."""
    # Use stdio for communication
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="proxy-status-server",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main()) 
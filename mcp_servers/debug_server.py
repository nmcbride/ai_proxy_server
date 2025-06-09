#!/usr/bin/env python3
"""
Debug MCP Server
Simple MCP server for testing and debugging tool calling.
Returns predictable values to verify tool execution.
"""

import asyncio
import time
from datetime import datetime
from typing import Any

import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server

# Global counter for testing
call_counter = 0

# Debug MCP server
server = Server("debug-server")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available debug tools."""
    return [
        types.Tool(
            name="get_debug_number",
            description="Returns a specific debug number (42) - useful for testing tool calls",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            },
        ),
        types.Tool(
            name="get_timestamp",
            description="Returns current timestamp - useful for verifying fresh tool calls",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            },
        ),
        types.Tool(
            name="echo_message",
            description="Echoes back the provided message - useful for testing parameter passing",
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Message to echo back"
                    }
                },
                "required": ["message"]
            },
        ),
        types.Tool(
            name="get_call_counter",
            description="Returns an incrementing counter - useful for testing multiple calls",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            },
        ),
        types.Tool(
            name="debug_math",
            description="Performs simple math operation - useful for testing parameter handling",
            inputSchema={
                "type": "object",
                "properties": {
                    "a": {
                        "type": "number",
                        "description": "First number"
                    },
                    "b": {
                        "type": "number",
                        "description": "Second number"
                    },
                    "operation": {
                        "type": "string",
                        "enum": ["add", "subtract", "multiply", "divide"],
                        "description": "Math operation to perform"
                    }
                },
                "required": ["a", "b", "operation"]
            },
        ),
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any] | None) -> list[types.TextContent]:
    """Handle tool calls."""
    global call_counter

    if name == "get_debug_number":
        return [
            types.TextContent(
                type="text",
                text="DEBUG_NUMBER: 42"
            )
        ]

    elif name == "get_timestamp":
        timestamp = datetime.now().isoformat()
        unix_time = int(time.time())
        return [
            types.TextContent(
                type="text",
                text=f"TIMESTAMP: {timestamp} (Unix: {unix_time})"
            )
        ]

    elif name == "echo_message":
        if not arguments or "message" not in arguments:
            return [
                types.TextContent(
                    type="text",
                    text="ERROR: No message provided to echo"
                )
            ]
        message = arguments["message"]
        return [
            types.TextContent(
                type="text",
                text=f"ECHO: {message}"
            )
        ]

    elif name == "get_call_counter":
        call_counter += 1
        return [
            types.TextContent(
                type="text",
                text=f"CALL_COUNTER: {call_counter}"
            )
        ]

    elif name == "debug_math":
        if not arguments:
            return [
                types.TextContent(
                    type="text",
                    text="ERROR: No arguments provided for math operation"
                )
            ]

        try:
            a = float(arguments.get("a", 0))
            b = float(arguments.get("b", 0))
            operation = arguments.get("operation", "add")

            if operation == "add":
                result = a + b
            elif operation == "subtract":
                result = a - b
            elif operation == "multiply":
                result = a * b
            elif operation == "divide":
                if b == 0:
                    return [
                        types.TextContent(
                            type="text",
                            text="ERROR: Cannot divide by zero"
                        )
                    ]
                result = a / b
            else:
                return [
                    types.TextContent(
                        type="text",
                        text=f"ERROR: Unknown operation '{operation}'"
                    )
                ]

            return [
                types.TextContent(
                    type="text",
                    text=f"MATH_RESULT: {a} {operation} {b} = {result}"
                )
            ]

        except (ValueError, TypeError) as e:
            return [
                types.TextContent(
                    type="text",
                    text=f"ERROR: Invalid number format - {str(e)}"
                )
            ]

    else:
        return [
            types.TextContent(
                type="text",
                text=f"ERROR: Unknown tool '{name}'"
            )
        ]

async def main():
    # Use stdio for communication
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="debug-server",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())

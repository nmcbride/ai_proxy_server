#!/usr/bin/env python3
"""
Example MCP Weather Server
A simple weather server for demonstration purposes.
"""

import asyncio
from typing import Any, Dict, List, cast

import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.types import (
    Tool,
)

# Mock weather data for demonstration
MOCK_WEATHER_DATA = {
    "new york": {
        "temperature": 72,
        "condition": "sunny",
        "humidity": 65,
        "wind_speed": 8,
        "forecast": [
            {"day": "today", "high": 75, "low": 65, "condition": "sunny"},
            {"day": "tomorrow", "high": 73, "low": 62, "condition": "partly cloudy"},
            {"day": "day after", "high": 68, "low": 58, "condition": "rainy"},
        ],
    },
    "london": {
        "temperature": 58,
        "condition": "cloudy",
        "humidity": 78,
        "wind_speed": 12,
        "forecast": [
            {"day": "today", "high": 62, "low": 54, "condition": "cloudy"},
            {"day": "tomorrow", "high": 59, "low": 51, "condition": "rainy"},
            {"day": "day after", "high": 64, "low": 56, "condition": "partly cloudy"},
        ],
    },
    "tokyo": {
        "temperature": 68,
        "condition": "partly cloudy",
        "humidity": 72,
        "wind_speed": 6,
        "forecast": [
            {"day": "today", "high": 71, "low": 63, "condition": "partly cloudy"},
            {"day": "tomorrow", "high": 74, "low": 66, "condition": "sunny"},
            {"day": "day after", "high": 69, "low": 61, "condition": "cloudy"},
        ],
    },
}

server: Server = Server("weather-server")


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """List available weather tools."""
    return [
        Tool(
            name="get_current_weather",
            description="Get current weather conditions for a city",
            inputSchema={
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "The city name (e.g., 'New York', 'London', 'Tokyo')",
                    },
                    "units": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "description": "Temperature units",
                        "default": "fahrenheit",
                    },
                },
                "required": ["city"],
            },
        ),
        Tool(
            name="get_weather_forecast",
            description="Get weather forecast for a city",
            inputSchema={
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "The city name (e.g., 'New York', 'London', 'Tokyo')",
                    },
                    "days": {
                        "type": "integer",
                        "description": "Number of days to forecast (1-7)",
                        "minimum": 1,
                        "maximum": 7,
                        "default": 3,
                    },
                    "units": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "description": "Temperature units",
                        "default": "fahrenheit",
                    },
                },
                "required": ["city"],
            },
        ),
        Tool(
            name="search_weather_alerts",
            description="Search for weather alerts in a given area",
            inputSchema={
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "Location to search for alerts",
                    },
                    "severity": {
                        "type": "string",
                        "enum": ["minor", "moderate", "severe", "extreme"],
                        "description": "Minimum alert severity",
                    },
                },
                "required": ["location"],
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Handle tool calls."""

    if name == "get_current_weather":
        city = arguments.get("city", "").lower()
        units = arguments.get("units", "fahrenheit")

        if city not in MOCK_WEATHER_DATA:
            return [
                types.TextContent(
                    type="text",
                    text=f"Weather data not available for {city}. Available cities: {', '.join(MOCK_WEATHER_DATA.keys())}",
                )
            ]

        weather = MOCK_WEATHER_DATA[city]
        temp_f = cast(int, weather["temperature"])

        if units == "celsius":
            temp: float = round((temp_f - 32) * 5 / 9, 1)
            unit_symbol = "°C"
        else:
            temp = temp_f
            unit_symbol = "°F"

        return [
            types.TextContent(
                type="text",
                text=f"Current weather in {city.title()}:\n"
                f"Temperature: {temp}{unit_symbol}\n"
                f"Condition: {weather['condition']}\n"
                f"Humidity: {weather['humidity']}%\n"
                f"Wind Speed: {weather['wind_speed']} mph",
            )
        ]

    elif name == "get_weather_forecast":
        city = arguments.get("city", "").lower()
        days = min(arguments.get("days", 3), 7)
        units = arguments.get("units", "fahrenheit")

        if city not in MOCK_WEATHER_DATA:
            return [
                types.TextContent(
                    type="text",
                    text=f"Weather data not available for {city}. Available cities: {', '.join(MOCK_WEATHER_DATA.keys())}",
                )
            ]

        weather = MOCK_WEATHER_DATA[city]
        forecast_data = cast(List[Dict[str, Any]], weather["forecast"])
        forecast = forecast_data[:days]

        forecast_text = f"Weather forecast for {city.title()} ({days} days):\n\n"

        for day_forecast in forecast:
            high_f = cast(int, day_forecast["high"])
            low_f = cast(int, day_forecast["low"])

            if units == "celsius":
                high: float = round((high_f - 32) * 5 / 9, 1)
                low: float = round((low_f - 32) * 5 / 9, 1)
                unit_symbol = "°C"
            else:
                high = high_f
                low = low_f
                unit_symbol = "°F"

            forecast_text += f"{cast(str, day_forecast['day']).title()}: {high}{unit_symbol}/{low}{unit_symbol}, {cast(str, day_forecast['condition'])}\n"

        return [types.TextContent(type="text", text=forecast_text)]

    elif name == "search_weather_alerts":
        location = arguments.get("location", "")
        severity = arguments.get("severity", "moderate")

        # Mock alert data
        alerts = [
            {
                "title": "Heat Advisory",
                "severity": "moderate",
                "description": "High temperatures expected",
                "area": location,
            }
        ]

        if severity in ["severe", "extreme"]:
            alerts = []  # No severe alerts in mock data

        if alerts:
            alert_text = f"Weather alerts for {location}:\n\n"
            for alert in alerts:
                alert_text += f"• {alert['title']} ({alert['severity']}): {alert['description']}\n"
        else:
            alert_text = f"No weather alerts found for {location} with severity {severity} or higher."

        return [types.TextContent(type="text", text=alert_text)]

    else:
        return [types.TextContent(type="text", text=f"Unknown tool: {name}")]


async def main() -> None:
    # Import here to avoid issues with event loops
    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="weather-server",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())

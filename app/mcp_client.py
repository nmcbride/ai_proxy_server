"""
Simple MCP Client for connecting to external MCP servers
"""

from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional

import structlog
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client

logger = structlog.get_logger()


class MCPServerConnection:
    """Represents a connection to a single MCP server"""

    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.session: Optional[ClientSession] = None
        self.tools: List[Dict[str, Any]] = []
        self.resources: List[Dict[str, Any]] = []
        self.prompts: List[Dict[str, Any]] = []
        self.connected = False
        self.exit_stack = AsyncExitStack()

    async def connect(self) -> bool:
        """Connect to the MCP server"""
        try:
            transport_type = self.config.get("transport", "stdio")

            if transport_type == "stdio":
                await self._connect_stdio()
            elif transport_type == "http":
                await self._connect_http()
            else:
                logger.error(
                    "Unsupported transport type",
                    server=self.name,
                    transport=transport_type,
                )
                return False

            # Initialize the session
            if self.session:
                await self.session.initialize()

            # Load capabilities
            await self._load_capabilities()

            self.connected = True
            logger.info(
                "Connected to MCP server",
                server=self.name,
                tools=len(self.tools),
                resources=len(self.resources),
                prompts=len(self.prompts),
            )
            return True

        except Exception as e:
            logger.error(
                "Failed to connect to MCP server", server=self.name, error=str(e)
            )
            return False

    async def _connect_stdio(self) -> None:
        """Connect using stdio transport"""
        params = StdioServerParameters(
            command=self.config["command"],
            args=self.config.get("args", []),
            env=self.config.get("env"),
        )

        read, write = await self.exit_stack.enter_async_context(stdio_client(params))

        self.session = await self.exit_stack.enter_async_context(
            ClientSession(read, write)
        )

    async def _connect_http(self) -> None:
        """Connect using HTTP transport"""
        read, write, _ = await self.exit_stack.enter_async_context(
            streamablehttp_client(
                self.config["server_url"], auth=self.config.get("auth")
            )
        )

        self.session = await self.exit_stack.enter_async_context(
            ClientSession(read, write)
        )

    async def _load_capabilities(self) -> None:
        """Load tools, resources, and prompts from the server"""
        if not self.session:
            return

        try:
            # Load tools
            tools_result = await self.session.list_tools()
            self.tools = [
                {
                    "name": tool.name,
                    "description": tool.description or "",
                    "inputSchema": tool.inputSchema,
                    "server": self.name,
                }
                for tool in tools_result.tools
            ]

            # Load resources
            try:
                resources_result = await self.session.list_resources()
                self.resources = [
                    {
                        "uri": resource.uri,
                        "name": resource.name,
                        "description": getattr(resource, "description", ""),
                        "server": self.name,
                    }
                    for resource in resources_result.resources
                ]
            except Exception:
                # Not all servers support resources
                self.resources = []

            # Load prompts
            try:
                prompts_result = await self.session.list_prompts()
                self.prompts = [
                    {
                        "name": prompt.name,
                        "description": prompt.description or "",
                        "arguments": [
                            {
                                "name": arg.name,
                                "description": arg.description or "",
                                "required": arg.required,
                            }
                            for arg in prompt.arguments or []
                        ],
                        "server": self.name,
                    }
                    for prompt in prompts_result.prompts
                ]
            except Exception:
                # Not all servers support prompts
                self.prompts = []

        except Exception as e:
            logger.error(
                "Failed to load capabilities from MCP server",
                server=self.name,
                error=str(e),
            )

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool on this server"""
        if not self.connected or not self.session:
            raise RuntimeError(f"Not connected to MCP server: {self.name}")

        try:
            result = await self.session.call_tool(tool_name, arguments)
            logger.info("Tool called successfully", server=self.name, tool=tool_name)
            return result.content
        except Exception as e:
            logger.error(
                "Tool call failed", server=self.name, tool=tool_name, error=str(e)
            )
            raise

    async def disconnect(self) -> None:
        """Disconnect from the server"""
        try:
            await self.exit_stack.aclose()
            self.connected = False
            self.session = None
            logger.info("Disconnected from MCP server", server=self.name)
        except Exception as e:
            logger.error(
                "Error disconnecting from MCP server", server=self.name, error=str(e)
            )


class MCPManager:
    """Simple MCP client manager for connecting to external MCP servers"""

    def __init__(self) -> None:
        self.servers: Dict[str, MCPServerConnection] = {}
        self.tool_registry: Dict[str, str] = {}  # tool_name -> server_name

    async def initialize(self, server_configs: Dict[str, Dict[str, Any]]) -> None:
        """Initialize connections to MCP servers"""
        logger.info("Initializing MCP connections", count=len(server_configs))

        for server_name, config in server_configs.items():
            try:
                connection = MCPServerConnection(server_name, config)
                success = await connection.connect()

                if success:
                    self.servers[server_name] = connection
                    # Register tools from this server
                    for tool in connection.tools:
                        tool_key = f"{server_name}:{tool['name']}"
                        self.tool_registry[tool_key] = server_name
                        # Also register without server prefix for convenience
                        if tool["name"] not in self.tool_registry:
                            self.tool_registry[tool["name"]] = server_name
                else:
                    logger.warning(
                        "Failed to connect to MCP server", server=server_name
                    )

            except Exception as e:
                logger.error(
                    "Error initializing MCP server", server=server_name, error=str(e)
                )

        logger.info(
            "MCP initialization complete",
            connected_servers=len(self.servers),
            total_tools=sum(len(s.tools) for s in self.servers.values()),
        )

    async def shutdown(self) -> None:
        """Shutdown all MCP connections"""
        logger.info("Shutting down MCP connections")

        for server in self.servers.values():
            await server.disconnect()

        self.servers.clear()
        self.tool_registry.clear()

    def get_all_tools(self) -> List[Dict[str, Any]]:
        """Get all available tools from all servers"""
        tools = []
        for server in self.servers.values():
            tools.extend(server.tools)
        return tools

    def get_all_resources(self) -> List[Dict[str, Any]]:
        """Get all available resources from all servers"""
        resources = []
        for server in self.servers.values():
            resources.extend(server.resources)
        return resources

    def get_all_prompts(self) -> List[Dict[str, Any]]:
        """Get all available prompts from all servers"""
        prompts = []
        for server in self.servers.values():
            prompts.extend(server.prompts)
        return prompts

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool on the appropriate server"""
        # Find which server has this tool
        server_name = self.tool_registry.get(tool_name)

        if not server_name:
            # Try with server prefix if original call failed
            for registered_name in self.tool_registry:
                if registered_name.endswith(f":{tool_name}"):
                    server_name = self.tool_registry[registered_name]
                    break

        if not server_name:
            raise ValueError(f"Tool not found: {tool_name}")

        if server_name not in self.servers:
            raise ValueError(f"Server not connected: {server_name}")

        # Extract actual tool name (remove server prefix if present)
        actual_tool_name = tool_name.split(":", 1)[-1]

        return await self.servers[server_name].call_tool(actual_tool_name, arguments)

    def format_tools_for_ai(self) -> List[Dict[str, Any]]:
        """Format tools for AI consumption (OpenAI function calling format)"""
        ai_tools = []

        for tool in self.get_all_tools():
            ai_tool = {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool.get("inputSchema", {}),
                },
            }
            ai_tools.append(ai_tool)

        return ai_tools

    def is_tool_call(self, tool_name: str) -> bool:
        """Check if a tool name corresponds to an MCP tool"""
        return tool_name in self.tool_registry

    def get_server_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all servers"""
        status = {}
        for name, server in self.servers.items():
            status[name] = {
                "connected": server.connected,
                "tools": len(server.tools),
                "resources": len(server.resources),
                "prompts": len(server.prompts),
                "transport": server.config.get("transport", "stdio"),
            }
        return status


# Global MCP manager instance
mcp_manager = MCPManager()

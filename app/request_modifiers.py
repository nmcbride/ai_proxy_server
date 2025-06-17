"""
Request modifications for the AI Proxy Server
"""

import re
from typing import Any, Dict, Optional

import structlog
from fastapi import Request

from app.config import settings
from app.mcp_client import mcp_manager

logger = structlog.get_logger()


class RequestModifier:
    """Request modifier to transform requests before sending to upstream"""

    def __init__(self) -> None:
        self.logger = logger.bind(component="request_modifier")

    async def modify_request(
        self, path: str, request_data: Dict[str, Any], request: Request, is_streaming: bool = False
    ) -> Dict[str, Any]:
        """
        Main method to modify requests based on the endpoint path

        Args:
            path: The API endpoint path (e.g., "/v1/chat/completions")
            request_data: The parsed request JSON data
            request: The FastAPI Request object
            is_streaming: Whether this is a streaming request (no tool calling possible)

        Returns:
            Modified request data
        """
        if not settings.ENABLE_REQUEST_MODIFICATION:
            return request_data

        self.logger.debug("Modifying request", path=path)

        # Route to specific modifier based on endpoint
        if path in ["/v1/chat/completions", "/chat/completions"]:
            return await self._modify_chat_completion(request_data, request, is_streaming)
        else:
            return await self._modify_generic(request_data, request, is_streaming)


    async def _modify_chat_completion(
        self, request_data: Dict[str, Any], request: Request, is_streaming: bool = False
    ) -> Dict[str, Any]:
        """
        Modify chat completion requests
        Example: Add system context, modify user messages, etc.
        """
        # # Add system context if configured
        # if settings.SYSTEM_CONTEXT and "messages" in request_data:
        #     messages = request_data["messages"]

        #     # Check if there's already a system message
        #     has_system_message = any(msg.get("role") == "system" for msg in messages)

        #     if not has_system_message:
        #         # Add system context at the beginning
        #         system_message = {"role": "system", "content": settings.SYSTEM_CONTEXT}
        #         request_data["messages"] = [system_message] + messages
        #         self.logger.info("Added system context to chat completion")

        # Add MCP tools if available
        # Tools work for:
        # 1. Non-streaming requests (always)
        # 2. Streaming requests when ENABLE_HYBRID_STREAMING=true
        should_add_tools = "messages" in request_data and (
            not is_streaming or settings.ENABLE_HYBRID_STREAMING
        )
        if should_add_tools:
            await self._add_mcp_tools(request_data)
            mode = "hybrid streaming" if is_streaming else "non-streaming"
            self.logger.debug(f"Added MCP tools to {mode} request")
        elif is_streaming:
            self.logger.info("Skipping MCP tools for pure streaming request (ENABLE_HYBRID_STREAMING=false)")

        return request_data

    async def _modify_generic(
        self, request_data: Dict[str, Any], request: Request, is_streaming: bool = False
    ) -> Dict[str, Any]:
        """
        Generic request modification for other endpoints
        """

        return request_data


    async def _add_mcp_tools(self, request_data: Dict[str, Any]) -> None:
        """Add MCP tools to the request if available"""
        try:
            # Get available MCP tools
            mcp_tools = mcp_manager.format_tools_for_ai()

            if mcp_tools:
                # Handle tool priority based on configuration
                existing_tools = request_data.get("tools", [])
                
                if settings.TOOL_PRIORITY == "client":
                    # Only add MCP tools if client didn't send any
                    if not existing_tools:
                        request_data["tools"] = mcp_tools
                        self.logger.debug(
                            "Added MCP tools to request (client had no tools)", 
                            tool_count=len(mcp_tools)
                        )
                    else:
                        self.logger.debug(
                            "Skipping MCP tools (client tools take priority)", 
                            client_tool_count=len(existing_tools)
                        )
                else:  # "proxy" priority (default)
                    # Proxy tools replace any client tools
                    request_data["tools"] = mcp_tools
                    if existing_tools:
                        self.logger.debug(
                            "Replaced client tools with MCP tools", 
                            client_tool_count=len(existing_tools),
                            mcp_tool_count=len(mcp_tools)
                        )
                    else:
                        self.logger.debug(
                            "Added MCP tools to request", 
                            tool_count=len(mcp_tools)
                        )

                # Ensure tool_choice allows auto selection (only if we added tools)
                if "tools" in request_data and request_data["tools"]:
                    if "tool_choice" not in request_data:
                        request_data["tool_choice"] = "auto"

                # Add information about available tools to system message
                tool_descriptions = []
                for tool in mcp_tools:
                    func = tool["function"]
                    tool_descriptions.append(f"- {func['name']}: {func['description']}")

                if tool_descriptions and "messages" in request_data:
                    messages = request_data["messages"]

                    # Create or update system message with tool info
                    tool_info = (
                        "You have access to the following tools:\n"
                        + "\n".join(tool_descriptions)
                        + "\n\nYou can call these tools when needed to help the user."
                        + "\n\nIMPORTANT: When a tool returns formatted content (like markdown), display it exactly as returned. Do not reformat, summarize, or modify tool responses - preserve all line breaks and formatting."
                    )

                    # Find existing system message or create new one
                    system_msg_index = None
                    for i, msg in enumerate(messages):
                        if msg.get("role") == "system":
                            system_msg_index = i
                            break

                    if system_msg_index is not None:
                        # Append to existing system message
                        existing_content = messages[system_msg_index].get("content", "")
                        messages[system_msg_index][
                            "content"
                        ] = f"{existing_content}\n\n{tool_info}"
                    else:
                        # Add new system message at the beginning
                        messages.insert(0, {"role": "system", "content": tool_info})

                    self.logger.debug("Added tool information to system message")

        except Exception as e:
            self.logger.error("Failed to add MCP tools to request", error=str(e))

    def _get_client_ip(self, request: Request) -> Optional[str]:
        """Utility function to get extract client IP from request"""

        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # Fallback to direct client IP
        if hasattr(request, "client") and request.client:
            return request.client.host

        return None

    def _preprocess_text(self, text: str) -> str:
        """
        Preprocess text for embeddings
        Example: Clean up formatting, remove excessive whitespace, etc.
        """
        # Basic text preprocessing
        cleaned = text.strip()

        # Remove excessive whitespace
        cleaned = re.sub(r"\s+", " ", cleaned)

        # Remove non-printable characters except newlines and tabs
        cleaned = "".join(
            char for char in cleaned if char.isprintable() or char in "\n\t"
        )

        return cleaned

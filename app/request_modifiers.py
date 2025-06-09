"""
Request modification examples for the AI Proxy Server
This module shows how to modify requests before they go to the LiteLLM upstream
"""

from typing import Any, Dict, List, Optional

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
        self, path: str, request_data: Dict[str, Any], request: Request
    ) -> Dict[str, Any]:
        """
        Main method to modify requests based on the endpoint path

        Args:
            path: The API endpoint path (e.g., "/v1/chat/completions")
            request_data: The parsed request JSON data
            request: The FastAPI Request object

        Returns:
            Modified request data
        """
        if not settings.ENABLE_REQUEST_MODIFICATION:
            return request_data

        self.logger.info("Modifying request", path=path)

        # Route to specific modifier based on endpoint
        if path == "/v1/chat/completions":
            return await self._modify_chat_completion(request_data, request)
        elif path == "/v1/completions":
            return await self._modify_completion(request_data, request)
        elif path == "/v1/embeddings":
            return await self._modify_embedding(request_data, request)
        else:
            return await self._modify_generic(request_data, request)

    async def _modify_chat_completion(
        self, request_data: Dict[str, Any], request: Request
    ) -> Dict[str, Any]:
        """
        Modify chat completion requests
        Example: Add system context, modify user messages, etc.
        """
        # Add MCP tools if available
        if "messages" in request_data:
            await self._add_mcp_tools(request_data)

        # Add system context if configured
        if settings.SYSTEM_CONTEXT and "messages" in request_data:
            messages = request_data["messages"]

            # Check if there's already a system message
            has_system_message = any(msg.get("role") == "system" for msg in messages)

            if not has_system_message:
                # Add system context at the beginning
                system_message = {"role": "system", "content": settings.SYSTEM_CONTEXT}
                request_data["messages"] = [system_message] + messages
                self.logger.info("Added system context to chat completion")

        # Example: Add user identification
        client_ip = self._get_client_ip(request)
        if client_ip and "messages" in request_data:
            # You could add user context or tracking here
            # For demo purposes, we'll add a comment to the last user message
            messages = request_data["messages"]
            for message in reversed(messages):
                if message.get("role") == "user":
                    original_content = message.get("content", "")
                    if isinstance(original_content, str):
                        # Add a subtle note about the client (for demo purposes)
                        message["content"] = (
                            f"{original_content}\n\n[Request from: {client_ip}]"
                        )
                    break

        # Example: Modify temperature based on model
        model = request_data.get("model", "")
        if "gpt-4" in model.lower() and "temperature" not in request_data:
            # Set conservative temperature for GPT-4 models
            request_data["temperature"] = 0.3
            self.logger.info("Set conservative temperature for GPT-4", temperature=0.3)

        # Example: Add default max_tokens if not specified
        if "max_tokens" not in request_data:
            request_data["max_tokens"] = 2048
            self.logger.info("Set default max_tokens", max_tokens=2048)

        # Example: Force JSON response format for certain models
        if (
            "gpt-4" in model.lower()
            and "json" in str(request_data.get("messages", [])).lower()
        ):
            request_data["response_format"] = {"type": "json_object"}
            self.logger.info("Forced JSON response format")

        return request_data

    async def _modify_completion(
        self, request_data: Dict[str, Any], request: Request
    ) -> Dict[str, Any]:
        """
        Modify text completion requests
        Example: Add prefixes, modify prompts, etc.
        """
        # Example: Add context prefix to prompt
        if settings.SYSTEM_CONTEXT and "prompt" in request_data:
            original_prompt = request_data["prompt"]
            if isinstance(original_prompt, str):
                request_data["prompt"] = (
                    f"{settings.SYSTEM_CONTEXT}\n\n{original_prompt}"
                )
                self.logger.info("Added system context prefix to completion prompt")
            elif isinstance(original_prompt, list):
                # Handle list of prompts
                modified_prompts = []
                for prompt in original_prompt:
                    if isinstance(prompt, str):
                        modified_prompts.append(
                            f"{settings.SYSTEM_CONTEXT}\n\n{prompt}"
                        )
                    else:
                        modified_prompts.append(prompt)
                request_data["prompt"] = modified_prompts
                self.logger.info("Added system context prefix to completion prompts")

        # Example: Set default parameters
        if "max_tokens" not in request_data:
            request_data["max_tokens"] = 1024
        if "temperature" not in request_data:
            request_data["temperature"] = 0.7

        return request_data

    async def _modify_embedding(
        self, request_data: Dict[str, Any], request: Request
    ) -> Dict[str, Any]:
        """
        Modify embedding requests
        Example: Preprocess text, add metadata, etc.
        """
        # Example: Preprocess input text
        if "input" in request_data:
            input_data = request_data["input"]
            if isinstance(input_data, str):
                # Clean and preprocess the text
                cleaned_text = self._preprocess_text(input_data)
                request_data["input"] = cleaned_text
                self.logger.info("Preprocessed embedding input text")
            elif isinstance(input_data, list):
                # Handle list of texts
                cleaned_texts = []
                for text in input_data:
                    if isinstance(text, str):
                        cleaned_texts.append(self._preprocess_text(text))
                    else:
                        cleaned_texts.append(text)
                request_data["input"] = cleaned_texts
                self.logger.info("Preprocessed embedding input texts")

        # Example: Set default model if not specified
        if "model" not in request_data:
            request_data["model"] = "text-embedding-ada-002"

        return request_data

    async def _modify_generic(
        self, request_data: Dict[str, Any], request: Request
    ) -> Dict[str, Any]:
        """
        Generic request modification for other endpoints
        """
        # Example: Add user tracking for all requests
        client_ip = self._get_client_ip(request)
        if client_ip:
            # Add metadata without affecting the core functionality
            request_data["_proxy_metadata"] = {
                "client_ip": client_ip,
                "timestamp": str(request.headers.get("x-request-timestamp", "")),
                "user_agent": str(request.headers.get("user-agent", "")),
            }

        return request_data

    async def _add_mcp_tools(self, request_data: Dict[str, Any]) -> None:
        """Add MCP tools to the request if available"""
        try:
            # Get available MCP tools
            mcp_tools = mcp_manager.format_tools_for_ai()

            if mcp_tools:
                # Add tools to request
                request_data["tools"] = request_data.get("tools", []) + mcp_tools

                # Ensure tool_choice allows auto selection
                if "tool_choice" not in request_data:
                    request_data["tool_choice"] = "auto"

                self.logger.info(
                    "Added MCP tools to request", tool_count=len(mcp_tools)
                )

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

                    self.logger.info("Added tool information to system message")

        except Exception as e:
            self.logger.error("Failed to add MCP tools to request", error=str(e))

    def _get_client_ip(self, request: Request) -> Optional[str]:
        """Extract client IP from request"""
        # Check for forwarded headers first
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
        import re

        cleaned = re.sub(r"\s+", " ", cleaned)

        # Remove non-printable characters except newlines and tabs
        cleaned = "".join(
            char for char in cleaned if char.isprintable() or char in "\n\t"
        )

        return cleaned


# Example of a more advanced request modifier
class AdvancedRequestModifier(RequestModifier):
    """
    Advanced request modifier with more sophisticated logic
    """

    def __init__(self) -> None:
        super().__init__()
        # You could load external configurations, ML models, etc.
        self.user_preferences: Dict[str, Any] = {}  # Could be loaded from database
        self.content_filters: List[str] = []  # Could be loaded from config

    async def _modify_chat_completion(
        self, request_data: Dict[str, Any], request: Request
    ) -> Dict[str, Any]:
        """Advanced chat completion modification"""
        # Call parent method first
        request_data = await super()._modify_chat_completion(request_data, request)

        # Add advanced features
        await self._apply_content_filtering(request_data)
        await self._apply_user_preferences(request_data, request)
        await self._add_conversation_context(request_data, request)

        return request_data

    async def _apply_content_filtering(self, request_data: Dict[str, Any]) -> None:
        """Apply content filtering to messages"""
        if "messages" in request_data:
            # Example: Filter out potentially harmful content
            # This is a simplified example - in production you'd use proper content filtering
            for message in request_data["messages"]:
                if message.get("role") == "user":
                    content = message.get("content", "")
                    if isinstance(content, str):
                        # Simple keyword filtering (replace with proper filtering)
                        filtered_content = self._filter_content(content)
                        if filtered_content != content:
                            message["content"] = filtered_content
                            self.logger.info(
                                "Applied content filtering to user message"
                            )

    async def _apply_user_preferences(
        self, request_data: Dict[str, Any], request: Request
    ) -> None:
        """Apply user-specific preferences"""
        user_id = request.headers.get("x-user-id")
        if user_id and user_id in self.user_preferences:
            prefs = self.user_preferences[user_id]

            # Apply user's preferred temperature
            if "preferred_temperature" in prefs:
                request_data["temperature"] = prefs["preferred_temperature"]

            # Apply user's preferred model if not specified
            if "preferred_model" in prefs and "model" not in request_data:
                request_data["model"] = prefs["preferred_model"]

            self.logger.info("Applied user preferences", user_id=user_id)

    async def _add_conversation_context(
        self, request_data: Dict[str, Any], request: Request
    ) -> None:
        """Add conversation context from session history"""
        session_id = request.headers.get("x-session-id")
        if session_id and "messages" in request_data:
            # In a real implementation, you'd retrieve conversation history
            # from a database or cache
            # For demo purposes, we'll just add a note
            context_message = {
                "role": "system",
                "content": f"[Conversation session: {session_id}]",
            }

            # Insert after any existing system messages
            messages = request_data["messages"]
            insert_index = 0
            for i, msg in enumerate(messages):
                if msg.get("role") == "system":
                    insert_index = i + 1
                else:
                    break

            messages.insert(insert_index, context_message)
            self.logger.info("Added conversation context", session_id=session_id)

    def _filter_content(self, content: str) -> str:
        """Simple content filtering"""
        # This is a very basic example - use proper content filtering in production
        inappropriate_words = [
            "harmful_word1",
            "harmful_word2",
        ]  # Replace with real list

        filtered_content = content
        for word in inappropriate_words:
            if word in filtered_content.lower():
                filtered_content = filtered_content.replace(word, "[FILTERED]")

        return filtered_content

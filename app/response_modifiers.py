"""
Response modification examples for the AI Proxy Server
This module shows how to modify responses before they are returned to the client
"""

import time
from typing import Any, Dict

import structlog
from fastapi import Request

from app.config import settings
from app.mcp_client import mcp_manager

logger = structlog.get_logger()


class ResponseModifier:
    """Response modifier to transform responses before sending to client"""

    def __init__(self) -> None:
        self.logger = logger.bind(component="response_modifier")

    async def modify_response(
        self,
        path: str,
        response_data: Dict[str, Any],
        request: Request,
        status_code: int,
    ) -> Dict[str, Any]:
        """
        Main method to modify responses based on the endpoint path

        Args:
            path: The API endpoint path (e.g., "/v1/chat/completions")
            response_data: The parsed response JSON data
            request: The FastAPI Request object
            status_code: HTTP status code from upstream

        Returns:
            Modified response data
        """
        if not settings.ENABLE_RESPONSE_MODIFICATION:
            return response_data

        self.logger.info("Modifying response", path=path, status_code=status_code)

        # Route to specific modifier based on endpoint
        if path == "/v1/chat/completions":
            return await self._modify_chat_completion(
                response_data, request, status_code
            )
        elif path == "/v1/completions":
            return await self._modify_completion(response_data, request, status_code)
        elif path == "/v1/embeddings":
            return await self._modify_embedding(response_data, request, status_code)
        elif path == "/v1/models":
            return await self._modify_models(response_data, request, status_code)
        else:
            return await self._modify_generic(response_data, request, status_code)

    async def _modify_chat_completion(
        self, response_data: Dict[str, Any], request: Request, status_code: int
    ) -> Dict[str, Any]:
        """
        Modify chat completion responses
        Example: Add metadata, filter content, modify usage stats, etc.
        """
        # Add proxy metadata
        response_data = await self._add_proxy_metadata(response_data, request)

        # Example: Add custom usage tracking
        if "usage" in response_data:
            usage = response_data["usage"]
            # Add custom metrics
            usage["proxy_processing_time"] = 0.1  # This would be calculated
            usage["proxy_version"] = "0.1.0"
            usage["proxy_model_override"] = False

        # Example: Post-process the assistant's response
        if "choices" in response_data:
            for choice in response_data["choices"]:
                if "message" in choice:
                    message = choice["message"]
                    if message.get("role") == "assistant":
                        # Post-process the content
                        content = message.get("content", "")
                        if isinstance(content, str):
                            processed_content = await self._post_process_content(
                                content, request
                            )
                            message["content"] = processed_content

        # Example: Add safety filters
        response_data = await self._apply_safety_filters(response_data, request)

        # Example: Add custom headers information
        if "model" in response_data:
            original_model = response_data["model"]
            response_data["_proxy_info"] = {
                "original_model": original_model,
                "proxy_timestamp": int(time.time()),
                "modifications_applied": [
                    "content_processing",
                    "safety_filters",
                    "metadata_addition",
                ],
            }

        return response_data

    async def _modify_completion(
        self, response_data: Dict[str, Any], request: Request, status_code: int
    ) -> Dict[str, Any]:
        """
        Modify text completion responses
        """
        # Add proxy metadata
        response_data = await self._add_proxy_metadata(response_data, request)

        # Example: Post-process completion choices
        if "choices" in response_data:
            for choice in response_data["choices"]:
                if "text" in choice:
                    original_text = choice["text"]
                    processed_text = await self._post_process_completion_text(
                        original_text, request
                    )
                    choice["text"] = processed_text

        # Example: Modify usage information
        if "usage" in response_data:
            usage = response_data["usage"]
            usage["proxy_processing_time"] = 0.05
            usage["content_filtered"] = False  # Would be set based on actual filtering

        return response_data

    async def _modify_embedding(
        self, response_data: Dict[str, Any], request: Request, status_code: int
    ) -> Dict[str, Any]:
        """
        Modify embedding responses
        """
        # Add proxy metadata
        response_data = await self._add_proxy_metadata(response_data, request)

        # Example: Add embedding metadata
        if "data" in response_data:
            for embedding_obj in response_data["data"]:
                if "embedding" in embedding_obj:
                    # You could normalize, filter, or transform embeddings here
                    # For demo, we'll just add metadata
                    embedding_obj["_proxy_processed"] = True
                    embedding_obj["_processing_timestamp"] = int(time.time())

        # Example: Add usage enhancement
        if "usage" in response_data:
            usage = response_data["usage"]
            usage["proxy_processing_time"] = 0.02
            usage["embedding_dimensions"] = len(
                response_data.get("data", [{}])[0].get("embedding", [])
            )

        return response_data

    async def _modify_models(
        self, response_data: Dict[str, Any], request: Request, status_code: int
    ) -> Dict[str, Any]:
        """
        Modify model list responses
        """
        # Example: Filter or modify available models
        if "data" in response_data:
            models = response_data["data"]

            # Example: Add custom model information
            for model in models:
                model["_proxy_supported"] = True
                model["_proxy_features"] = [
                    "request_modification",
                    "response_modification",
                ]

            # Example: Add a custom proxy model
            custom_model = {
                "id": "proxy-enhanced-gpt-3.5-turbo",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "ai-proxy-server",
                "_proxy_supported": True,
                "_proxy_features": [
                    "enhanced_context",
                    "safety_filtering",
                    "custom_prompting",
                ],
                "_is_proxy_model": True,
            }
            models.append(custom_model)

            self.logger.info("Added custom proxy model to model list")

        # Add proxy metadata
        response_data = await self._add_proxy_metadata(response_data, request)

        return response_data

    async def _modify_generic(
        self, response_data: Dict[str, Any], request: Request, status_code: int
    ) -> Dict[str, Any]:
        """
        Generic response modification for other endpoints
        """
        # Add basic proxy metadata
        response_data = await self._add_proxy_metadata(response_data, request)

        return response_data

    async def _add_proxy_metadata(
        self, response_data: Dict[str, Any], request: Request
    ) -> Dict[str, Any]:
        """Add proxy metadata to response"""
        # Only add metadata if it doesn't interfere with the response structure
        if isinstance(response_data, dict) and "error" not in response_data:
            # Add metadata that doesn't conflict with OpenAI response format
            proxy_metadata = {
                "proxy_server": "ai-proxy-server",
                "proxy_version": "0.1.0",
                "processing_timestamp": int(time.time()),
            }

            # Add to a custom field that won't interfere with client parsing
            response_data["_proxy"] = proxy_metadata

        return response_data

    async def _post_process_content(self, content: str, request: Request) -> str:
        """
        Post-process assistant content
        Example: Format responses, add disclaimers, etc.
        """
        processed_content = content

        # Example: Add disclaimers for certain types of responses
        if any(
            keyword in content.lower() for keyword in ["medical", "legal", "financial"]
        ):
            disclaimer = "\n\n*Note: This response is for informational purposes only and should not be considered professional advice.*"
            processed_content += disclaimer
            self.logger.info("Added disclaimer to response")

        # Example: Format code blocks better
        if "```" in content:
            # Enhanced code formatting could go here
            processed_content = self._enhance_code_formatting(processed_content)

        # Example: Replace certain terms or correct common issues
        processed_content = self._apply_content_corrections(processed_content)

        return processed_content

    async def _post_process_completion_text(self, text: str, request: Request) -> str:
        """Post-process completion text"""
        processed_text = text

        # Example: Clean up formatting
        processed_text = processed_text.strip()

        # Example: Apply content guidelines
        processed_text = self._apply_content_corrections(processed_text)

        return processed_text

    async def _apply_safety_filters(
        self, response_data: Dict[str, Any], request: Request
    ) -> Dict[str, Any]:
        """
        Apply safety filters to responses
        """
        if "choices" in response_data:
            for choice in response_data["choices"]:
                if "message" in choice:
                    message = choice["message"]
                    content = message.get("content", "")

                    # Example: Check for potentially harmful content
                    if self._contains_harmful_content(content):
                        # Replace with a safe message
                        message["content"] = (
                            "I apologize, but I cannot provide that type of content. Please let me know if I can help you with something else."
                        )
                        # Add a flag to indicate filtering occurred
                        choice["_content_filtered"] = True
                        self.logger.warning("Content filtered due to safety concerns")

        return response_data

    def _enhance_code_formatting(self, content: str) -> str:
        """Enhance code formatting in responses"""
        # Example: Add language hints or improve formatting
        # This is a simplified example
        enhanced_content = content

        # Could add syntax highlighting hints, better formatting, etc.
        return enhanced_content

    def _apply_content_corrections(self, content: str) -> str:
        """Apply content corrections and improvements"""
        corrected_content = content

        # Example: Fix common AI response issues
        corrections = {
            "I'm an AI": "I'm an AI assistant",
            "I can't browse the internet": "I don't have access to real-time internet data",
            # Add more corrections as needed
        }

        for incorrect, correct in corrections.items():
            corrected_content = corrected_content.replace(incorrect, correct)

        return corrected_content

    def _contains_harmful_content(self, content: str) -> bool:
        """
        Check if content contains harmful material
        This is a simplified example - use proper content filtering in production
        """
        harmful_indicators = [
            "generate harmful content",
            "illegal activities",
            # Add more indicators
        ]

        content_lower = content.lower()
        return any(indicator in content_lower for indicator in harmful_indicators)


class AdvancedResponseModifier(ResponseModifier):
    """
    Advanced response modifier with more sophisticated features
    """

    def __init__(self) -> None:
        super().__init__()
        self.content_analyzer = None  # Could be an ML model for content analysis
        self.user_preferences: Dict[str, Any] = {}  # Could be loaded from database
        self.response_cache: Dict[str, Any] = {}  # Could be a Redis cache

    async def _modify_chat_completion(
        self, response_data: Dict[str, Any], request: Request, status_code: int
    ) -> Dict[str, Any]:
        """Advanced chat completion response modification"""
        # Call parent method first
        response_data = await super()._modify_chat_completion(
            response_data, request, status_code
        )

        # Add advanced features
        await self._add_personalization(response_data, request)
        await self._add_analytics_tracking(response_data, request)
        await self._enhance_response_quality(response_data, request)

        return response_data

    async def _add_personalization(
        self, response_data: Dict[str, Any], request: Request
    ) -> None:
        """Add personalization to responses"""
        user_id = request.headers.get("x-user-id")
        if user_id and user_id in self.user_preferences:
            prefs = self.user_preferences[user_id]

            # Example: Adjust response style based on user preferences
            if "response_style" in prefs and "choices" in response_data:
                for choice in response_data["choices"]:
                    if "message" in choice:
                        content = choice["message"].get("content", "")
                        if content:
                            # Adjust tone/style based on preferences
                            styled_content = self._apply_response_style(
                                content, prefs["response_style"]
                            )
                            choice["message"]["content"] = styled_content

            self.logger.info("Applied personalization", user_id=user_id)

    async def _add_analytics_tracking(
        self, response_data: Dict[str, Any], request: Request
    ) -> None:
        """Add analytics and tracking information"""
        # Track response metrics
        analytics_data = {
            "request_timestamp": int(time.time()),
            "response_length": len(str(response_data)),
            "user_agent": request.headers.get("user-agent", ""),
            "endpoint": "/v1/chat/completions",
        }

        # Add to response metadata
        if "_proxy" in response_data:
            response_data["_proxy"]["analytics"] = analytics_data

        # In a real implementation, you'd send this to an analytics service
        self.logger.info("Analytics data collected", **analytics_data)

    async def _enhance_response_quality(
        self, response_data: Dict[str, Any], request: Request
    ) -> None:
        """Enhance response quality using various techniques"""
        if "choices" in response_data:
            for choice in response_data["choices"]:
                if "message" in choice:
                    content = choice["message"].get("content", "")
                    if content:
                        # Apply quality enhancements
                        enhanced_content = await self._apply_quality_enhancements(
                            content
                        )
                        choice["message"]["content"] = enhanced_content

    def _apply_response_style(self, content: str, style: str) -> str:
        """Apply response style based on user preference"""
        if style == "formal":
            # Make response more formal
            content = content.replace("don't", "do not")
            content = content.replace("can't", "cannot")
            content = content.replace("won't", "will not")
        elif style == "casual":
            # Make response more casual
            content = content.replace("do not", "don't")
            content = content.replace("cannot", "can't")

        return content

    async def _apply_quality_enhancements(self, content: str) -> str:
        """Apply various quality enhancements to content"""
        enhanced_content = content

        # Example: Improve formatting
        enhanced_content = self._improve_formatting(enhanced_content)

        # Example: Add helpful context
        enhanced_content = self._add_helpful_context(enhanced_content)

        return enhanced_content

    def _improve_formatting(self, content: str) -> str:
        """Improve content formatting"""
        # Example improvements
        formatted_content = content

        # Ensure proper spacing after periods
        import re

        formatted_content = re.sub(r"\.([A-Z])", r". \1", formatted_content)

        # Ensure proper bullet point formatting
        formatted_content = re.sub(r"^\*", "•", formatted_content, flags=re.MULTILINE)

        return formatted_content

    def _add_helpful_context(self, content: str) -> str:
        """Add helpful context to responses where appropriate"""
        enhanced_content = content

        # Example: Add follow-up suggestions for certain types of responses
        if "tutorial" in content.lower() or "how to" in content.lower():
            enhanced_content += "\n\n💡 Would you like me to elaborate on any specific step or provide additional examples?"

        return enhanced_content

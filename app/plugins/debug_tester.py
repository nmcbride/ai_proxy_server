"""Debug Tester Plugin for verifying plugin system functionality."""

import time
from typing import Any, Dict

from app.plugin_system.registry import register_plugin

# Default configuration (used as fallback if no config provided)
DEFAULT_CONFIG = {
    "debug_context": {"magic_number": 42, "magic_word": "PYTHON"},
    "debug_response": {
        "verification_token": "DEBUG_ACTIVE",
        "system_status": "plugin_system_operational",
    },
    "add_timestamp": True,
}


@register_plugin(
    name="debug_tester",
    endpoints=["/v1/chat/completions"],
    priority=10,
    hook="before_request",
    description="Adds known debug values for testing and verifying plugin functionality",
    version="2.0.0",
)
def before_request_handler(
    request_data: Dict[str, Any], context: Dict[str, Any]
) -> Dict[str, Any]:
    """Add debug context to the request."""
    # Get configuration from context, fall back to defaults
    config = context.get("config", DEFAULT_CONFIG)

    # Check if plugin is disabled
    if config.get("enabled", True) is False:
        return request_data

    # Add debug information to system message
    debug_context = config.get("debug_context", DEFAULT_CONFIG["debug_context"])
    if debug_context and "messages" in request_data:
        messages = request_data["messages"]

        # Create debug context string
        debug_info = []

        # Add configured debug values
        if "magic_number" in debug_context:
            debug_info.append(f"MAGIC_NUMBER={debug_context['magic_number']}")

        if "magic_word" in debug_context:
            debug_info.append(f"MAGIC_WORD={debug_context['magic_word']}")

        # Add test mode if specified
        if "test_mode" in debug_context:
            debug_info.append(f"DEBUG_TEST_MODE: {debug_context['test_mode']}")

        # Add instruction if specified
        if "instruction" in debug_context:
            debug_info.append(f"IMPORTANT: {debug_context['instruction']}")

        # Add timestamp if enabled
        if config.get("add_timestamp", DEFAULT_CONFIG["add_timestamp"]):
            debug_info.append(f"DEBUG_TIMESTAMP: {int(time.time())}")

        if debug_info:
            debug_text = "\n".join(debug_info)

            # Find existing system message or create one
            system_message_found = False
            for message in messages:
                if message.get("role") == "system":
                    # Append to existing system message
                    message["content"] += f"\n\nDEBUG INFO:\n{debug_text}"
                    system_message_found = True
                    break

            if not system_message_found:
                # Create new system message with debug info
                debug_system_message = {
                    "role": "system",
                    "content": f"DEBUG INFO:\n{debug_text}",
                }
                request_data["messages"] = [debug_system_message] + messages

    return request_data


@register_plugin(
    name="debug_tester",
    endpoints=["/v1/chat/completions"],
    priority=10,
    hook="after_request",
    description="Adds debug metadata to response for testing plugin functionality",
    version="2.0.0",
)
def after_request_handler(
    response_data: Dict[str, Any], context: Dict[str, Any]
) -> Dict[str, Any]:
    """Add debug metadata to the response."""
    # Get configuration from context, fall back to defaults
    config = context.get("config", DEFAULT_CONFIG)

    # Check if plugin is disabled
    if config.get("enabled", True) is False:
        return response_data

    # Add debug metadata
    if "debug_test" not in response_data:
        response_data["debug_test"] = {}

    debug_metadata = response_data["debug_test"]

    # Add configured debug values to response
    debug_response = config.get("debug_response", DEFAULT_CONFIG["debug_response"])
    if debug_response:
        debug_metadata.update(debug_response)

    # Add processing info
    debug_metadata["plugin_executed"] = True
    debug_metadata["execution_time"] = int(time.time())
    debug_metadata["plugin_name"] = "debug_tester"
    debug_metadata["plugin_version"] = "2.0.0"

    # Add context info for debugging
    debug_metadata["endpoint"] = context.get("endpoint", "unknown")
    debug_metadata["config_source"] = "yaml" if "config" in context else "default"

    return response_data

"""Example User Plugin demonstrating the registry system."""

from typing import Any, Dict

from app.plugin_system.registry import register_plugin


@register_plugin(
    name="example_user_plugin",
    endpoints=["*"],  # Apply to all endpoints
    priority=30,  # Lower priority than system plugins (runs after priority=10)
    hook="before_request",
    description="Example user plugin that adds custom headers",
    version="1.0.0",
)
def add_custom_header(
    request_data: Dict[str, Any], context: Dict[str, Any]
) -> Dict[str, Any]:
    """Add a custom header to identify this as a user-modified request."""
    if "headers" not in request_data:
        request_data["headers"] = {}

    request_data["headers"]["X-User-Plugin"] = "example_user_plugin_v1.0.0"
    request_data["headers"]["X-Plugin-Type"] = "user_created"
    request_data["headers"]["X-Processed-Endpoint"] = context.get("endpoint", "unknown")

    return request_data


@register_plugin(
    name="example_user_plugin",
    endpoints=["/v1/chat/completions"],
    priority=30,  # Lower priority (runs after priority=10)
    hook="after_request",
    description="Example user plugin that adds response metadata",
    version="1.0.0",
)
def add_response_metadata(
    response_data: Dict[str, Any], context: Dict[str, Any]
) -> Dict[str, Any]:
    """Add metadata to show this response was processed by a user plugin."""
    if "user_plugin_info" not in response_data:
        response_data["user_plugin_info"] = {}

    response_data["user_plugin_info"]["processed_by"] = "example_user_plugin"
    response_data["user_plugin_info"]["plugin_type"] = "user_created"
    response_data["user_plugin_info"][
        "message"
    ] = "This response was enhanced by a user plugin!"
    response_data["user_plugin_info"]["processed_endpoint"] = context.get(
        "endpoint", "unknown"
    )

    return response_data

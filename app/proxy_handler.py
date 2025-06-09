"""
Core proxy request handling
"""

import json
from typing import Union

import httpx
import structlog
from fastapi import HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from app.config import settings
from app.request_modifiers import RequestModifier
from app.response_modifiers import ResponseModifier
from app.tool_handler import handle_tool_calls
from app.utils import generate_request_id, get_client_ip

logger = structlog.get_logger()

# Initialize request and response modifiers
request_modifier = RequestModifier()
response_modifier = ResponseModifier()


async def proxy_request(
    method: str,
    path: str,
    request: Request,
    client: httpx.AsyncClient,
    modify_request: bool = True,
    modify_response: bool = True,
) -> Union[Response, StreamingResponse]:
    """
    Core proxy functionality to forward requests to LiteLLM upstream
    """
    proxy_request_id = generate_request_id()
    client_ip = get_client_ip(request)

    logger.info(
        "Proxying request",
        proxy_request_id=proxy_request_id,
        method=method,
        path=path,
        client_ip=client_ip,
    )

    try:
        # Get request body
        body = await request.body()

        # Parse and modify request if enabled
        is_streaming_request = False
        request_data = None
        if body:
            try:
                request_data = json.loads(body)
                # Check if this is a streaming request
                is_streaming_request = request_data.get("stream", False)

                if modify_request:
                    modified_data = await request_modifier.modify_request(
                        path, request_data, request, is_streaming=is_streaming_request
                    )
                    body = json.dumps(modified_data).encode()
            except json.JSONDecodeError:
                logger.warning(
                    "Failed to parse request body as JSON",
                    proxy_request_id=proxy_request_id,
                )

        # Prepare upstream URL
        upstream_url = f"{settings.LITELLM_BASE_URL.rstrip('/')}{path}"

        # Prepare headers (remove hop-by-hop headers)
        headers = dict(request.headers)
        headers.pop("host", None)
        headers.pop("content-length", None)
        if body:
            headers["content-length"] = str(len(body))

        # Add any additional headers for LiteLLM
        if settings.LITELLM_API_KEY:
            headers["authorization"] = f"Bearer {settings.LITELLM_API_KEY}"

        # Make initial upstream request
        if is_streaming_request:
            # For streaming requests, we can't do tool calling, so pass through directly
            logger.info(
                "Handling streaming request (no tool calling)",
                proxy_request_id=proxy_request_id,
            )

            # Build request for pure streaming proxy
            upstream_request = client.build_request(
                method=method,
                url=upstream_url,
                headers=headers,
                content=body,
                params=request.query_params,
            )

            # Send with streaming enabled
            upstream_response = await client.send(upstream_request, stream=True)

            # Return pure streaming response preserving upstream headers and status
            return StreamingResponse(
                upstream_response.aiter_raw(),
                status_code=upstream_response.status_code,
                headers=upstream_response.headers,
                background=BackgroundTask(upstream_response.aclose),
            )
        else:
            # Non-streaming request with potential tool calling
            upstream_request = client.build_request(
                method=method,
                url=upstream_url,
                headers=headers,
                content=body,
                params=request.query_params,
            )
            upstream_response = await client.send(upstream_request)

        # Handle regular responses with potential tool calling
        response_content = upstream_response.content
        response_headers = dict(upstream_response.headers)

        # Parse response for tool call handling
        if response_content:
            try:
                response_data = json.loads(response_content)

                # Check if this is a chat completion with tool calls
                if (
                    path in ["/v1/chat/completions", "/chat/completions"]
                    and "choices" in response_data
                    and response_data["choices"]
                ):

                    # Check for tool calls in the response
                    first_choice = response_data["choices"][0]
                    message = first_choice.get("message", {})
                    tool_calls = message.get("tool_calls", [])

                    if tool_calls:
                        logger.info(
                            "Tool calls detected, executing MCP tools",
                            proxy_request_id=proxy_request_id,
                            tool_count=len(tool_calls),
                        )

                        # Execute tool calls and get final response
                        final_response_data = await handle_tool_calls(
                            response_data,
                            request_data,
                            client,
                            upstream_url,
                            headers,
                            proxy_request_id,
                        )
                        response_content = json.dumps(final_response_data).encode()
                        response_headers.pop("content-length", None)
                        response_headers.pop("Content-Length", None)
                    else:
                        # No tool calls, apply regular response modification
                        if modify_response:
                            modified_data = await response_modifier.modify_response(
                                path,
                                response_data,
                                request,
                                upstream_response.status_code,
                            )
                            response_content = json.dumps(modified_data).encode()
                            response_headers.pop("content-length", None)
                            response_headers.pop("Content-Length", None)
                else:
                    # Not a chat completion, apply regular response modification
                    if modify_response:
                        modified_data = await response_modifier.modify_response(
                            path, response_data, request, upstream_response.status_code
                        )
                        response_content = json.dumps(modified_data).encode()
                        response_headers.pop("content-length", None)
                        response_headers.pop("Content-Length", None)

            except json.JSONDecodeError:
                logger.warning(
                    "Failed to parse response body as JSON",
                    proxy_request_id=proxy_request_id,
                )

        return Response(
            content=response_content,
            status_code=upstream_response.status_code,
            headers=response_headers,
        )

    except httpx.TimeoutException as e:
        logger.error("Upstream request timeout", proxy_request_id=proxy_request_id)
        raise HTTPException(status_code=504, detail="Upstream request timeout") from e
    except httpx.RequestError as e:
        logger.error(
            "Upstream request error", proxy_request_id=proxy_request_id, error=str(e)
        )
        raise HTTPException(status_code=502, detail="Upstream request failed") from e
    except Exception as e:
        logger.error(
            "Unexpected error in proxy", proxy_request_id=proxy_request_id, error=str(e)
        )
        raise HTTPException(status_code=500, detail="Internal server error") from e

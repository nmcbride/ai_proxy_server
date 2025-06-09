"""
Core proxy request handling
"""

import asyncio
import json
from typing import Any, Dict, Union

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


async def handle_hybrid_streaming_request(
    request_data: Dict[str, Any],
    client: httpx.AsyncClient,
    upstream_url: str,
    headers: Dict[str, str],
    proxy_request_id: str,
    method: str,
    request: Request,
    path: str,
    modify_response: bool,
) -> StreamingResponse:
    """
    Handle hybrid streaming: tool calling in non-streaming mode + streaming final response

    Flow:
    1. Convert streaming request to non-streaming for tool calling
    2. Execute tool calling rounds (if any tools are called)
    3. Convert final response back to streaming format for client
    """
    # Step 1: Create non-streaming version of request for tool calling
    non_streaming_request = request_data.copy()
    non_streaming_request["stream"] = False

    # Add MCP tools to the non-streaming request for tool calling
    logger.info(
        "Adding MCP tools to hybrid streaming request",
        proxy_request_id=proxy_request_id,
    )
    non_streaming_request = await request_modifier.modify_request(
        path, non_streaming_request, request, is_streaming=False
    )

    logger.info(
        "Converting to non-streaming for tool calling phase",
        proxy_request_id=proxy_request_id,
    )

    # Prepare non-streaming request body
    non_streaming_body = json.dumps(non_streaming_request).encode()
    non_streaming_headers = headers.copy()
    non_streaming_headers["content-length"] = str(len(non_streaming_body))

    # Step 2: Execute tool calling phase in non-streaming mode
    upstream_request = client.build_request(
        method=method,
        url=upstream_url,
        headers=non_streaming_headers,
        content=non_streaming_body,
        params=request.query_params,
    )
    upstream_response = await client.send(upstream_request)

    # Parse initial response
    response_data = json.loads(upstream_response.content)

    # Check for tool calls and execute them if present
    if (
        path in ["/v1/chat/completions", "/chat/completions"]
        and "choices" in response_data
        and response_data["choices"]
    ):
        first_choice = response_data["choices"][0]
        message = first_choice.get("message", {})
        tool_calls = message.get("tool_calls", [])

        if tool_calls:
            logger.info(
                "Tool calls detected in hybrid streaming, executing tools",
                proxy_request_id=proxy_request_id,
                tool_count=len(tool_calls),
            )

            # Execute tool calls and get final response
            response_data = await handle_tool_calls(
                response_data,
                non_streaming_request,
                client,
                upstream_url,
                non_streaming_headers,
                proxy_request_id,
            )
        elif modify_response:
            # No tool calls, apply regular response modification
            response_data = await response_modifier.modify_response(
                path, response_data, request, upstream_response.status_code
            )
    elif modify_response:
        # Not a chat completion, apply regular response modification
        response_data = await response_modifier.modify_response(
            path, response_data, request, upstream_response.status_code
        )

    # Step 3: Convert final response to streaming format
    logger.info(
        "Converting final response to streaming format",
        proxy_request_id=proxy_request_id,
    )

    # Extract the assistant's final message content
    final_content = ""
    if "choices" in response_data and response_data["choices"]:
        choice = response_data["choices"][0]
        message = choice.get("message", {})
        final_content = message.get("content", "")

    # Create streaming response chunks
    async def generate_streaming_chunks():
        """Generate OpenAI-compatible streaming chunks from final content"""
        import time

        # Send initial chunk with role
        chunk_data = {
            "id": response_data.get("id", ""),
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": response_data.get("model", ""),
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant"},
                    "finish_reason": None,
                }
            ],
        }
        yield f"data: {json.dumps(chunk_data)}\n\n"

        # Stream content in chunks (simulate natural streaming)
        words = final_content.split()
        for i, word in enumerate(words):
            chunk_data = {
                "id": response_data.get("id", ""),
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": response_data.get("model", ""),
                "choices": [
                    {
                        "index": 0,
                        "delta": {"content": word + (" " if i < len(words) - 1 else "")},
                        "finish_reason": None,
                    }
                ],
            }
            yield f"data: {json.dumps(chunk_data)}\n\n"

            # Small delay to simulate natural streaming
            await asyncio.sleep(0.02)

        # Send final chunk with finish reason
        chunk_data = {
            "id": response_data.get("id", ""),
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": response_data.get("model", ""),
            "choices": [
                {
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop",
                }
            ],
        }
        yield f"data: {json.dumps(chunk_data)}\n\n"
        yield "data: [DONE]\n\n"

    # Return streaming response
    return StreamingResponse(
        generate_streaming_chunks(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


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
            # Check if hybrid streaming is enabled
            if settings.ENABLE_HYBRID_STREAMING:
                logger.info(
                    "Handling hybrid streaming request (tool calling + streaming final response)",
                    proxy_request_id=proxy_request_id,
                )
                return await handle_hybrid_streaming_request(
                    request_data,
                    client,
                    upstream_url,
                    headers,
                    proxy_request_id,
                    method,
                    request,
                    path,
                    modify_response,
                )
            else:
                # For pure streaming requests, we can't do tool calling, so pass through directly
                logger.info(
                    "Handling pure streaming request (no tool calling)",
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

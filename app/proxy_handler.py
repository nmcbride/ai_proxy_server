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
from app.profiler import create_profiler, cleanup_profiler, get_profiler
from app.request_modifiers import RequestModifier
from app.response_modifiers import ResponseModifier
from app.tool_handler import handle_tool_calls
from app.utils import generate_request_id, get_client_ip

logger = structlog.get_logger()

# Initialize request and response modifiers
request_modifier = RequestModifier()
response_modifier = ResponseModifier()

# Import plugin manager from main (will be initialized there)
plugin_manager = None


def set_plugin_manager(pm):
    """Set the plugin manager instance from main.py"""
    global plugin_manager
    plugin_manager = pm


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
    # Get profiler for this request
    profiler = get_profiler(proxy_request_id)
    
    # Step 1: Create non-streaming version of request for tool calling
    async with profiler.time_phase("Converting to Non-Streaming") if profiler else None:
        non_streaming_request = request_data.copy()
        non_streaming_request["stream"] = False

        # Add MCP tools and apply plugins to the non-streaming request for tool calling
        logger.debug(
            "Applying request modifications for hybrid streaming request",
            proxy_request_id=proxy_request_id,
        )
        # Apply plugin system
        if plugin_manager:
            context = {"endpoint": path}
            non_streaming_request = plugin_manager.execute_before_request_plugins(
                non_streaming_request, context
            )
        # Apply core MCP functionality
        non_streaming_request = await request_modifier.modify_request(
            path, non_streaming_request, request, is_streaming=False
        )

        logger.debug(
            "Converting to non-streaming for tool calling phase",
            proxy_request_id=proxy_request_id,
        )

        # Prepare non-streaming request body
        non_streaming_body = json.dumps(non_streaming_request).encode()
        non_streaming_headers = headers.copy()
        non_streaming_headers["content-length"] = str(len(non_streaming_body))

    # Step 2: Execute tool calling phase in non-streaming mode
    async with profiler.time_phase("Initial Tool-Calling Request") if profiler else None:
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
    async with profiler.time_phase("Processing Tool-Call Response") if profiler else None:
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
                # Apply plugin system
                if plugin_manager:
                    context = {"endpoint": path}
                    response_data = plugin_manager.execute_after_request_plugins(
                        response_data, context
                    )
                # Apply core response modification
                response_data = await response_modifier.modify_response(
                    path, response_data, request, upstream_response.status_code
                )
        elif modify_response:
            # Not a chat completion, apply regular response modification
            # Apply plugin system
            if plugin_manager:
                context = {"endpoint": path}
                response_data = plugin_manager.execute_after_request_plugins(
                    response_data, context
                )
            # Apply core response modification
            response_data = await response_modifier.modify_response(
                path, response_data, request, upstream_response.status_code
            )

    # Step 3: Convert final response to streaming format
    logger.debug(
        "Converting final response to streaming format",
        proxy_request_id=proxy_request_id,
    )

    # Get profiler for this request and add model metadata from response
    profiler = get_profiler(proxy_request_id)
    if profiler and "model" in response_data:
        profiler.set_metadata("model", response_data["model"])

    # Extract the assistant's final message content
    async with profiler.time_phase("Extracting Streaming Content") if profiler else None:
        final_content = ""
        if "choices" in response_data and response_data["choices"]:
            choice = response_data["choices"][0]
            message = choice.get("message", {})
            final_content = message.get("content", "")

    # Create streaming response chunks
    async def generate_streaming_chunks():
        """Generate OpenAI-compatible streaming chunks from final content"""
        import time

        chunk_start_time = time.perf_counter()
        total_chunks = 0

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
        total_chunks += 1

        # Stream content in character chunks (preserves all formatting)
        chunk_size = 30  # Characters per chunk for natural streaming feel
        
        for i in range(0, len(final_content), chunk_size):
            chunk_text = final_content[i:i + chunk_size]
            
            chunk_data = {
                "id": response_data.get("id", ""),
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": response_data.get("model", ""),
                "choices": [
                    {
                        "index": 0,
                        "delta": {"content": chunk_text},
                        "finish_reason": None,
                    }
                ],
            }
            yield f"data: {json.dumps(chunk_data)}\n\n"
            total_chunks += 1

        # Send final chunk with finish_reason
        final_chunk_data = {
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
        yield f"data: {json.dumps(final_chunk_data)}\n\n"
        total_chunks += 1

        # Send the final data terminator
        yield "data: [DONE]\n\n"

        # Record chunk creation timing with summary metadata
        chunk_creation_time = time.perf_counter() - chunk_start_time
        chunk_creation_ms = round(chunk_creation_time * 1000, 2)
        content_length = len(final_content)
        avg_chunk_size = content_length / total_chunks if total_chunks > 0 else 0

        if profiler:
            profiler.start_timing(
                "Hybrid Chunk Creation Total",
                duration_ms=chunk_creation_ms,
                total_chunks=total_chunks,
                content_length=content_length,
                avg_chunk_size=round(avg_chunk_size, 1)
            ).finish()

    return StreamingResponse(
        generate_streaming_chunks(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Credentials": "true",
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

    # Create profiler for this request
    profiler = create_profiler(proxy_request_id)

    logger.debug(
        "Proxying request",
        proxy_request_id=proxy_request_id,
        method=method,
        path=path,
        client_ip=client_ip,
    )

    try:
        # Get request body
        async with profiler.time_phase("Reading Request Data"):
            body = await request.body()

        # Parse and modify request if enabled
        is_streaming_request = False
        request_data = None
        if body:
            try:
                async with profiler.time_phase("Parsing Request JSON", data_size=len(body)):
                    request_data = json.loads(body)
                    # Check if this is a streaming request
                    is_streaming_request = request_data.get("stream", False)
                    
                    # Add model information to profiler metadata if available
                    if "model" in request_data:
                        profiler.set_metadata("model", request_data["model"])

                if modify_request:
                    async with profiler.time_phase("Processing Request"):
                        # Apply plugin system
                        if plugin_manager:
                            async with profiler.time_phase("Running Pre-Processing Plugins", plugin_count=len(plugin_manager.before_request_plugins) if hasattr(plugin_manager, 'before_request_plugins') else 0):
                                context = {"endpoint": path}
                                modified_data = plugin_manager.execute_before_request_plugins(
                                    request_data, context
                                )
                        else:
                            modified_data = request_data
                        # Apply core MCP functionality
                        async with profiler.time_phase("Processing Request"):
                            modified_data = await request_modifier.modify_request(
                                path, modified_data, request, is_streaming=is_streaming_request
                            )
                    async with profiler.time_phase("Serializing Request JSON", data_size=len(json.dumps(modified_data))):
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
                async with profiler.time_phase("Streaming to AI Provider", method=method, url=upstream_url):
                    upstream_response = await client.send(upstream_request, stream=True)

                # Return pure streaming response with cleaned headers
                # Clean headers to avoid conflicts with middleware
                async with profiler.time_phase("Processing Streaming Headers"):
                    clean_headers = {}
                    for key, value in upstream_response.headers.items():
                        # Skip headers that might conflict with middleware
                        if key.lower() not in ["server", "date"]:
                            clean_headers[key] = value
                    
                    # Add CORS headers since StreamingResponse bypasses middleware
                    clean_headers["Access-Control-Allow-Origin"] = "*"
                    clean_headers["Access-Control-Allow-Headers"] = "*"
                    clean_headers["Access-Control-Allow-Methods"] = "*"
                    clean_headers["Access-Control-Allow-Credentials"] = "true"
                
                return StreamingResponse(
                    upstream_response.aiter_raw(),
                    status_code=upstream_response.status_code,
                    headers=clean_headers,
                    background=BackgroundTask(upstream_response.aclose),
                )
        else:
            # Non-streaming request with potential tool calling
            async with profiler.time_phase("Building Upstream Request"):
                upstream_request = client.build_request(
                    method=method,
                    url=upstream_url,
                    headers=headers,
                    content=body,
                    params=request.query_params,
                )
            async with profiler.time_phase("Calling AI Provider", method=method, url=upstream_url):
                upstream_response = await client.send(upstream_request)

        # Handle regular responses with potential tool calling
        response_content = upstream_response.content
        response_headers = dict(upstream_response.headers)

        # Parse response for tool call handling
        if response_content:
            try:
                async with profiler.time_phase("Parsing AI Response", data_size=len(response_content)):
                    response_data = json.loads(response_content)
                    
                    # Add model information from response to profiler metadata if available
                    if "model" in response_data:
                        profiler.set_metadata("model", response_data["model"])

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
                        async with profiler.time_phase("Processing Tool Calls", tool_count=len(tool_calls)):
                            final_response_data = await handle_tool_calls(
                                response_data,
                                request_data,
                                client,
                                upstream_url,
                                headers,
                                proxy_request_id,
                            )
                        async with profiler.time_phase("Serializing Final Response", data_size=len(json.dumps(final_response_data))):
                            response_content = json.dumps(final_response_data).encode()
                        response_headers.pop("content-length", None)
                        response_headers.pop("Content-Length", None)
                    else:
                        # No tool calls, apply regular response modification
                        if modify_response:
                            async with profiler.time_phase("Processing Response"):
                                # Apply plugin system
                                if plugin_manager:
                                    async with profiler.time_phase("Running Post-Processing Plugins", plugin_count=len(plugin_manager.after_request_plugins) if hasattr(plugin_manager, 'after_request_plugins') else 0):
                                        context = {"endpoint": path}
                                        modified_data = plugin_manager.execute_after_request_plugins(
                                            response_data, context
                                        )
                                else:
                                    modified_data = response_data
                                # Apply core response modification
                                async with profiler.time_phase("Processing Response"):
                                    modified_data = await response_modifier.modify_response(
                                        path,
                                        modified_data,
                                        request,
                                        upstream_response.status_code,
                                    )
                            async with profiler.time_phase("Serializing Final Response", data_size=len(json.dumps(modified_data))):
                                response_content = json.dumps(modified_data).encode()
                            response_headers.pop("content-length", None)
                            response_headers.pop("Content-Length", None)
                else:
                    # Not a chat completion, apply regular response modification
                    if modify_response:
                        async with profiler.time_phase("Processing Response"):
                            # Apply plugin system
                            if plugin_manager:
                                async with profiler.time_phase("Running Post-Processing Plugins", plugin_count=len(plugin_manager.after_request_plugins) if hasattr(plugin_manager, 'after_request_plugins') else 0):
                                    context = {"endpoint": path}
                                    modified_data = plugin_manager.execute_after_request_plugins(
                                        response_data, context
                                    )
                            else:
                                modified_data = response_data
                            # Apply core response modification
                            async with profiler.time_phase("Processing Response"):
                                modified_data = await response_modifier.modify_response(
                                    path, modified_data, request, upstream_response.status_code
                                )
                        async with profiler.time_phase("Serializing Final Response", data_size=len(json.dumps(modified_data))):
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
    finally:
        # Log profiling summary but keep profiler active for dashboard viewing
        profiler = get_profiler(proxy_request_id)
        if profiler:
            profile_summary = profiler.get_summary()
            # Log summary at debug level
            logger.debug(
                "Request profiling summary",
                proxy_request_id=proxy_request_id,
                total_time_ms=profile_summary["total_time_ms"],
                phase_count=profile_summary["phase_count"],
                breakdown=profile_summary["breakdown"],
            )

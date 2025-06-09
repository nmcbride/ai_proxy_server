"""
FastAPI Proxy Server for OpenAI v1 API Endpoints with LiteLLM Upstream
"""

import json
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, Optional, Union

import httpx
import structlog
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.background import BackgroundTask

from app.config import settings
from app.mcp_client import mcp_manager
from app.mcp_config import mcp_config
from app.middleware import LoggingMiddleware, ProxyMiddleware
from app.request_modifiers import RequestModifier
from app.response_modifiers import ResponseModifier
from app.utils import generate_request_id, get_client_ip

# Configure structured logging
logger = structlog.get_logger()

# Global HTTP client for upstream requests
http_client: Optional[httpx.AsyncClient] = None


async def handle_tool_calls(
    initial_response: Dict[str, Any],
    original_request: Dict[str, Any],
    client: httpx.AsyncClient,
    upstream_url: str,
    headers: Dict[str, str],
    proxy_request_id: str,
) -> Dict[str, Any]:
    """
    Handle tool calls by executing MCP tools and sending results back to LLM
    Supports multi-step tool calling (e.g., Context7's resolve-library-id -> get-library-docs)
    """
    messages = original_request.get("messages", []).copy()
    current_response = initial_response
    max_tool_rounds = 5  # Prevent infinite loops
    tool_round = 0

    while tool_round < max_tool_rounds:
        tool_round += 1

        # Check if current response has tool calls
        if not ("choices" in current_response and current_response["choices"]):
            break

        first_choice = current_response["choices"][0]
        assistant_message = first_choice["message"]
        tool_calls = assistant_message.get("tool_calls", [])

        if not tool_calls:
            # No more tool calls, we're done
            logger.info(
                "No more tool calls, returning final response",
                proxy_request_id=proxy_request_id,
                total_rounds=tool_round - 1,
            )
            break

        logger.info(
            "Processing tool calls",
            proxy_request_id=proxy_request_id,
            round=tool_round,
            tool_count=len(tool_calls),
        )

        # Add the assistant's tool call message to conversation
        messages.append(assistant_message)

        # Execute all tool calls in this round
        tool_results = []
        for tool_call in tool_calls:
            if tool_call.get("type") == "function":
                function_info = tool_call["function"]
                function_name = function_info["name"]
                tool_call_id = tool_call["id"]

                try:
                    # Parse arguments
                    arguments_str = function_info.get("arguments", "{}")
                    arguments = json.loads(arguments_str) if arguments_str else {}

                    logger.info(
                        "Executing MCP tool",
                        proxy_request_id=proxy_request_id,
                        round=tool_round,
                        tool=function_name,
                        arguments=list(arguments.keys()),
                    )

                    # Call the MCP tool
                    result = await mcp_manager.call_tool(function_name, arguments)

                    # Format result as string (MCP returns content objects)
                    if isinstance(result, list) and result:
                        # MCP returns list of content objects
                        result_text = ""
                        for content in result:
                            if hasattr(content, "text"):
                                result_text += content.text
                            elif isinstance(content, dict) and "text" in content:
                                result_text += content["text"]
                            else:
                                result_text += str(content)
                    else:
                        result_text = str(result)

                    tool_results.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": result_text,
                        }
                    )

                    logger.info(
                        "MCP tool executed successfully",
                        proxy_request_id=proxy_request_id,
                        round=tool_round,
                        tool=function_name,
                    )

                except Exception as e:
                    logger.error(
                        "MCP tool execution failed",
                        proxy_request_id=proxy_request_id,
                        round=tool_round,
                        tool=function_name,
                        error=str(e),
                    )

                    # Add error result
                    tool_results.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": f"Error executing tool {function_name}: {str(e)}",
                        }
                    )

        # Add all tool results to conversation
        messages.extend(tool_results)

        # Create new request payload WITH tools still available for next round
        new_request = original_request.copy()
        new_request["messages"] = messages
        # Keep tools available for multi-step tool calling

        logger.info(
            "Sending tool results back to LLM for next round",
            proxy_request_id=proxy_request_id,
            round=tool_round,
            message_count=len(messages),
        )

        # Make next request with tool results
        new_body = json.dumps(new_request).encode()

        # Update headers
        new_headers = headers.copy()
        new_headers["content-length"] = str(len(new_body))

        # Build and send request for tool calling follow-up
        tool_request = client.build_request(
            method="POST",
            url=upstream_url,
            headers=new_headers,
            content=new_body,
        )
        next_response = await client.send(tool_request)

        # Parse response for next round
        current_response = json.loads(next_response.content)

    if tool_round >= max_tool_rounds:
        logger.warning(
            "Max tool rounds reached, stopping",
            proxy_request_id=proxy_request_id,
            max_rounds=max_tool_rounds,
        )

    logger.info(
        "Tool calling completed",
        proxy_request_id=proxy_request_id,
        total_rounds=tool_round - 1,
    )

    return current_response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager"""
    global http_client

    # Startup
    logger.info("Starting AI Proxy Server")
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(settings.REQUEST_TIMEOUT),
        follow_redirects=True,
        limits=httpx.Limits(
            max_connections=settings.MAX_CONNECTIONS,
            max_keepalive_connections=settings.MAX_KEEPALIVE_CONNECTIONS,
        ),
    )

    # Initialize MCP connections
    try:
        mcp_server_configs = mcp_config.load_config()
        if mcp_server_configs:
            await mcp_manager.initialize(mcp_server_configs)
            logger.info("MCP integration initialized", servers=len(mcp_server_configs))
        else:
            logger.info("No MCP servers configured")
    except Exception as e:
        logger.error("Failed to initialize MCP integration", error=str(e))

    yield

    # Shutdown
    logger.info("Shutting down AI Proxy Server")

    # Shutdown MCP connections
    try:
        await mcp_manager.shutdown()
    except Exception as e:
        logger.error("Error shutting down MCP connections", error=str(e))

    if http_client:
        await http_client.aclose()


app = FastAPI(
    title="AI Proxy Server",
    description="FastAPI proxy server for OpenAI v1 API endpoints with LiteLLM upstream",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add custom middleware
app.add_middleware(LoggingMiddleware)
app.add_middleware(ProxyMiddleware)

# Initialize request and response modifiers
request_modifier = RequestModifier()
response_modifier = ResponseModifier()


async def get_http_client() -> httpx.AsyncClient:
    """Dependency to get the HTTP client"""
    if http_client is None:
        raise HTTPException(status_code=500, detail="HTTP client not initialized")
    return http_client


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


@app.api_route("/health", methods=["GET"])
async def health_check() -> dict:
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": time.time()}


@app.api_route("/mcp/status", methods=["GET"])
async def mcp_status() -> dict:
    """Get MCP server status and available tools"""
    try:
        status = mcp_manager.get_server_status()
        tools = mcp_manager.get_all_tools()

        return {
            "servers": status,
            "tools": [
                {
                    "name": tool["name"],
                    "description": tool["description"],
                    "server": tool["server"],
                }
                for tool in tools
            ],
            "total_tools": len(tools),
            "connected_servers": len([s for s in status.values() if s["connected"]]),
        }
    except Exception as e:
        logger.error("Error getting MCP status", error=str(e))
        return {"error": str(e)}


@app.api_route("/v1/models", methods=["GET"], response_model=None)
async def list_models(
    request: Request,
    client: httpx.AsyncClient = Depends(get_http_client),
) -> Union[Response, StreamingResponse]:
    """List available models"""
    return await proxy_request("GET", "/v1/models", request, client)


@app.api_route("/models", methods=["GET"], response_model=None)
async def list_models_no_v1(
    request: Request,
    client: httpx.AsyncClient = Depends(get_http_client),
) -> Union[Response, StreamingResponse]:
    """List available models (OpenAI client compatibility)"""
    return await proxy_request("GET", "/v1/models", request, client)


@app.api_route("/v1/chat/completions", methods=["POST"], response_model=None)
async def chat_completions(
    request: Request,
    client: httpx.AsyncClient = Depends(get_http_client),
) -> Union[Response, StreamingResponse]:
    """
    Chat completions endpoint with request/response modification
    This is where you can add context, modify prompts, etc.
    """
    return await proxy_request("POST", "/v1/chat/completions", request, client)


@app.api_route("/chat/completions", methods=["POST"], response_model=None)
async def chat_completions_no_v1(
    request: Request,
    client: httpx.AsyncClient = Depends(get_http_client),
) -> Union[Response, StreamingResponse]:
    """Chat completions endpoint (OpenAI client compatibility)"""
    return await proxy_request("POST", "/v1/chat/completions", request, client)


@app.api_route("/v1/completions", methods=["POST"], response_model=None)
async def completions(
    request: Request,
    client: httpx.AsyncClient = Depends(get_http_client),
) -> Union[Response, StreamingResponse]:
    """
    Text completions endpoint with request/response modification
    """
    return await proxy_request("POST", "/v1/completions", request, client)


@app.api_route("/completions", methods=["POST"], response_model=None)
async def completions_no_v1(
    request: Request,
    client: httpx.AsyncClient = Depends(get_http_client),
) -> Union[Response, StreamingResponse]:
    """Text completions endpoint (OpenAI client compatibility)"""
    return await proxy_request("POST", "/v1/completions", request, client)


@app.api_route("/v1/embeddings", methods=["POST"], response_model=None)
async def embeddings(
    request: Request,
    client: httpx.AsyncClient = Depends(get_http_client),
) -> Union[Response, StreamingResponse]:
    """
    Embeddings endpoint with request/response modification
    """
    return await proxy_request("POST", "/v1/embeddings", request, client)


@app.api_route("/embeddings", methods=["POST"], response_model=None)
async def embeddings_no_v1(
    request: Request,
    client: httpx.AsyncClient = Depends(get_http_client),
) -> Union[Response, StreamingResponse]:
    """Embeddings endpoint (OpenAI client compatibility)"""
    return await proxy_request("POST", "/v1/embeddings", request, client)


@app.api_route("/v1/moderations", methods=["POST"], response_model=None)
async def moderations(
    request: Request,
    client: httpx.AsyncClient = Depends(get_http_client),
) -> Union[Response, StreamingResponse]:
    """
    Moderations endpoint
    """
    return await proxy_request("POST", "/v1/moderations", request, client)


@app.api_route("/v1/images/generations", methods=["POST"], response_model=None)
async def image_generations(
    request: Request,
    client: httpx.AsyncClient = Depends(get_http_client),
) -> Union[Response, StreamingResponse]:
    """
    Image generations endpoint
    """
    return await proxy_request("POST", "/v1/images/generations", request, client)


@app.api_route("/v1/audio/speech", methods=["POST"], response_model=None)
async def audio_speech(
    request: Request,
    client: httpx.AsyncClient = Depends(get_http_client),
) -> Union[Response, StreamingResponse]:
    """
    Audio speech endpoint
    """
    return await proxy_request("POST", "/v1/audio/speech", request, client)


@app.api_route("/v1/audio/transcriptions", methods=["POST"], response_model=None)
async def audio_transcriptions(
    request: Request,
    client: httpx.AsyncClient = Depends(get_http_client),
) -> Union[Response, StreamingResponse]:
    """
    Audio transcriptions endpoint
    """
    return await proxy_request("POST", "/v1/audio/transcriptions", request, client)


@app.api_route("/v1/audio/translations", methods=["POST"], response_model=None)
async def audio_translations(
    request: Request,
    client: httpx.AsyncClient = Depends(get_http_client),
) -> Union[Response, StreamingResponse]:
    """
    Audio translations endpoint
    """
    return await proxy_request("POST", "/v1/audio/translations", request, client)


# Catch-all route for any other v1 endpoints
@app.api_route(
    "/v1/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    response_model=None,
)
async def catch_all_v1(
    path: str,
    request: Request,
    client: httpx.AsyncClient = Depends(get_http_client),
) -> Union[Response, StreamingResponse]:
    """
    Catch-all route for other OpenAI v1 endpoints
    """
    full_path = f"/v1/{path}"
    return await proxy_request(request.method, full_path, request, client)


# Debug catch-all route for any missed requests
@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    response_model=None,
)
async def debug_catch_all(
    path: str,
    request: Request,
) -> JSONResponse:
    """
    Debug catch-all route to see what requests are being missed
    """
    logger.warning(
        "Unmatched request",
        method=request.method,
        path=path,
        url=str(request.url),
        headers=dict(request.headers),
    )
    return JSONResponse(
        status_code=404,
        content={
            "error": {
                "message": f"Path not found: {request.method} {path}",
                "type": "not_found",
                "debug_info": {
                    "method": request.method,
                    "path": path,
                    "url": str(request.url),
                    "headers": dict(request.headers),
                },
            }
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Custom HTTP exception handler"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"message": exc.detail, "type": "proxy_error"}},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info" if not settings.DEBUG else "debug",
    )

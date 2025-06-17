"""
FastAPI Proxy Server for OpenAI v1 API Endpoints with LiteLLM Upstream
"""

import time
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional, Union

import httpx
import structlog
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from app.config import settings
from app.mcp_client import mcp_manager
from app.mcp_config import mcp_config
from app.middleware import LoggingMiddleware, ProxyMiddleware
from app.plugin_system import PluginManager
from app.profiling_endpoint import profiling_router
from app.proxy_handler import proxy_request, set_plugin_manager

# Configure structured logging with file output
def configure_logging():
    """Configure structlog to write to both stdout and file"""
    import sys
    from pathlib import Path
    
    # Create logs directory if it doesn't exist
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Configure standard logging to write to file
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(logs_dir / "ai_proxy_server.log"),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

# Configure logging on import
configure_logging()

# Suppress watchfiles.main INFO logging only in DEBUG mode to prevent "1 change detected" spam
if settings.DEBUG:
    watchfiles_logger = logging.getLogger('watchfiles.main')
    watchfiles_logger.setLevel(logging.WARNING)

logger = structlog.get_logger()

# Global HTTP client for upstream requests
http_client: Optional[httpx.AsyncClient] = None

# Global plugin manager
plugin_manager = PluginManager()


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

    # Initialize plugin system
    try:
        counts = plugin_manager.load_plugins()
        set_plugin_manager(plugin_manager)  # Share with proxy_handler
        logger.info("Plugin system initialized", counts=counts)
    except Exception as e:
        logger.error("Failed to initialize plugin system", error=str(e))

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

# Add profiling router
app.include_router(profiling_router)

async def get_http_client() -> httpx.AsyncClient:
    """Dependency to get the HTTP client"""
    if http_client is None:
        raise HTTPException(status_code=500, detail="HTTP client not initialized")
    return http_client


@app.api_route("/health", methods=["GET"])
async def health_check() -> dict:
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": time.time()}


@app.api_route("/config", methods=["GET"])
async def get_config() -> dict:
    """Get current server configuration"""
    try:
        # Use Pydantic's model_dump() to properly serialize the settings
        config = settings.model_dump()

        # Handle long string values by truncating them
        for key, value in config.items():
            if isinstance(value, str) and len(value) > 100:
                config[key] = value[:100] + "..."

        return config
    except Exception as e:
        logger.error("Error getting configuration", error=str(e))
        return {"error": f"Failed to get configuration: {str(e)}"}



@app.api_route("/debug/mcp/status", methods=["GET"])
async def get_mcp_status() -> dict:
    """Get MCP server status and available tools"""
    return {
        "servers": mcp_manager.get_server_status(),
        "tools": mcp_manager.get_all_tools(),
        "resources": mcp_manager.get_all_resources(),
        "prompts": mcp_manager.get_all_prompts(),
        "tool_registry": mcp_manager.tool_registry,
        "formatted_tools": mcp_manager.format_tools_for_ai(),
    }


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


@app.api_route("/plugins/status", methods=["GET"])
async def plugin_status() -> dict:
    """Get plugin status and information"""
    try:
        return plugin_manager.get_plugin_status()
    except Exception as e:
        logger.error("Error getting plugin status", error=str(e))
        return {"error": str(e)}


@app.api_route("/models", methods=["GET"], response_model=None)
@app.api_route("/v1/models", methods=["GET"], response_model=None)
async def list_models(
    request: Request,
    client: httpx.AsyncClient = Depends(get_http_client),
) -> Union[Response, StreamingResponse]:
    """List available models"""
    return await proxy_request("GET", "/v1/models", request, client)


@app.api_route("/chat/completions", methods=["POST"], response_model=None)
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
        reload_excludes=["logs/", "logs/*", "*.log", "logs/*.log", "__pycache__/", "*.pyc"],
        log_level="info" if not settings.DEBUG else "debug",
    )

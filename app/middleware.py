"""
Custom middleware for the AI Proxy Server
"""

import time
import uuid
from typing import Awaitable, Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger()


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for request/response logging"""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Generate request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Start timer
        start_time = time.perf_counter()

        # Log request
        logger.info(
            "Request started",
            request_id=request_id,
            method=request.method,
            url=str(request.url),
            client_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

        try:
            # Process request
            response = await call_next(request)

            # Calculate processing time
            process_time = time.perf_counter() - start_time

            # Log response
            logger.debug(
                "Request completed",
                request_id=request_id,
                status_code=response.status_code,
                process_time=process_time,
            )

            # Add request ID and processing time to response headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = str(process_time)

            return response

        except Exception as e:
            # Calculate processing time for errors
            process_time = time.perf_counter() - start_time

            # Log error
            logger.error(
                "Request failed",
                request_id=request_id,
                error=str(e),
                process_time=process_time,
            )

            raise


class ProxyMiddleware(BaseHTTPMiddleware):
    """Middleware for proxy-specific functionality"""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Add proxy headers
        if not hasattr(request.state, "proxy_headers"):
            request.state.proxy_headers = {}

        # Add timestamp
        request.state.proxy_headers["X-Proxy-Timestamp"] = str(int(time.time()))

        # Add proxy version
        request.state.proxy_headers["X-Proxy-Version"] = "0.1.0"

        # Process request
        response = await call_next(request)

        # Add proxy headers to response
        for header_name, header_value in request.state.proxy_headers.items():
            response.headers[header_name] = header_value

        # Add anti-buffering headers for streaming responses
        if response.headers.get("content-type", "").startswith("text/event-stream"):
            response.headers["cache-control"] = "no-cache, no-store, must-revalidate"
            response.headers["pragma"] = "no-cache"
            response.headers["expires"] = "0"
            response.headers["x-accel-buffering"] = "no"  # Nginx
            response.headers["x-apache-buffering"] = "no"  # Apache

        return response

"""
Utility functions for the AI Proxy Server
"""

import uuid
from typing import Optional

from fastapi import Request


def generate_request_id() -> str:
    """Generate a unique request ID"""
    return str(uuid.uuid4())


def get_client_ip(request: Request) -> Optional[str]:
    """
    Extract the real client IP address from the request
    Handles X-Forwarded-For and X-Real-IP headers for proxy scenarios
    """
    # Check for X-Forwarded-For header (most common)
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs, take the first one
        return forwarded_for.split(",")[0].strip()

    # Check for X-Real-IP header
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()

    # Check for CF-Connecting-IP (Cloudflare)
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip.strip()

    # Fallback to direct client IP
    if hasattr(request, "client") and request.client:
        return request.client.host

    return None


def sanitize_headers(headers: dict) -> dict:
    """
    Sanitize headers before forwarding to upstream
    Removes hop-by-hop headers and sensitive information
    """
    # Headers that should not be forwarded
    hop_by_hop_headers = {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "host",  # Will be set to upstream host
        "content-length",  # Will be recalculated
    }

    sanitized = {}
    for key, value in headers.items():
        if key.lower() not in hop_by_hop_headers:
            sanitized[key] = value

    return sanitized


def format_error_response(
    message: str, error_type: str = "proxy_error", status_code: int = 500
) -> dict:
    """
    Format an error response in OpenAI API format
    """
    return {"error": {"message": message, "type": error_type, "code": status_code}}

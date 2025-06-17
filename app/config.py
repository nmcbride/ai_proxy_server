"""
Configuration settings for the AI Proxy Server
"""

from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""

    # Server configuration
    HOST: str = Field(default="0.0.0.0", validation_alias="HOST")
    PORT: int = Field(default=8000, validation_alias="PORT")
    DEBUG: bool = Field(default=False, validation_alias="DEBUG")

    # LiteLLM upstream configuration
    LITELLM_BASE_URL: str = Field(
        default="http://localhost:4000", validation_alias="LITELLM_BASE_URL"
    )
    LITELLM_API_KEY: str = Field(default="", validation_alias="LITELLM_API_KEY")

    # HTTP client configuration
    REQUEST_TIMEOUT: float = Field(
        default=300.0, validation_alias="REQUEST_TIMEOUT"
    )  # 5 minutes
    MAX_CONNECTIONS: int = Field(default=100, validation_alias="MAX_CONNECTIONS")
    MAX_KEEPALIVE_CONNECTIONS: int = Field(
        default=20, validation_alias="MAX_KEEPALIVE_CONNECTIONS"
    )

    # CORS configuration
    ALLOWED_ORIGINS: List[str] = Field(
        default=["*"], validation_alias="ALLOWED_ORIGINS"
    )

    # Logging configuration (handled by structlog and uvicorn)

    # Request/Response modification settings
    ENABLE_REQUEST_MODIFICATION: bool = Field(
        default=True, validation_alias="ENABLE_REQUEST_MODIFICATION"
    )
    ENABLE_RESPONSE_MODIFICATION: bool = Field(
        default=True, validation_alias="ENABLE_RESPONSE_MODIFICATION"
    )

    # Tool calling configuration
    MAX_TOOL_ROUNDS: int = Field(
        default=5,
        validation_alias="MAX_TOOL_ROUNDS",
        description="Maximum number of tool calling rounds to prevent infinite loops"
    )
    TOOL_EXECUTION_TIMEOUT: float = Field(
        default=30.0,
        validation_alias="TOOL_EXECUTION_TIMEOUT",
        description="Timeout for individual tool execution in seconds"
    )
    ENABLE_HYBRID_STREAMING: bool = Field(
        default=False,
        validation_alias="ENABLE_HYBRID_STREAMING",
        description="Enable hybrid streaming mode (tool calling + streaming final response)"
    )
    HYBRID_STREAMING_DELAY: float = Field(
        default=0.02,
        validation_alias="HYBRID_STREAMING_DELAY",
        description="Delay between chunks in hybrid streaming mode (seconds, 0 for no delay)"
    )
    HYBRID_STREAMING_CHUNK_SIZE: int = Field(
        default=30,
        validation_alias="HYBRID_STREAMING_CHUNK_SIZE",
        description="Number of characters per chunk in hybrid streaming mode"
    )

    # Tool priority configuration
    TOOL_PRIORITY: str = Field(
        default="proxy",
        validation_alias="TOOL_PRIORITY",
        description="Tool priority: 'proxy' (proxy tools only) or 'client' (client tools take priority, proxy tools as fallback)"
    )

    class Config:
        # Find .env file relative to project root (one level up from app/)
        env_file = Path(__file__).parent.parent / ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # Ignore extra environment variables not defined as fields
        env_prefix = ""  # No prefix for now, but you could use "PROXY_" if desired


# Global settings instance
settings = Settings()

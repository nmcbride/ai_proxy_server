"""
Configuration settings for the AI Proxy Server
"""

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

    # Logging configuration
    LOG_LEVEL: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    LOG_FORMAT: str = Field(
        default="json", validation_alias="LOG_FORMAT"
    )  # json or console

    # Request/Response modification settings
    ENABLE_REQUEST_MODIFICATION: bool = Field(
        default=True, validation_alias="ENABLE_REQUEST_MODIFICATION"
    )
    ENABLE_RESPONSE_MODIFICATION: bool = Field(
        default=True, validation_alias="ENABLE_RESPONSE_MODIFICATION"
    )

    # Context injection settings
    SYSTEM_CONTEXT: str = Field(
        default="",
        validation_alias="SYSTEM_CONTEXT",
        description="Additional system context to inject into chat completions",
    )



    # Rate limiting (optional, not implemented yet)
    ENABLE_RATE_LIMITING: bool = Field(
        default=False, validation_alias="ENABLE_RATE_LIMITING"
    )
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = Field(
        default=60, validation_alias="RATE_LIMIT_REQUESTS_PER_MINUTE"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Global settings instance
settings = Settings()

"""
Layer F: Shared services (python-dotenv, Secret Manager SDK, OpenTelemetry)
Configuration management and environment variable loading
"""

import os
from functools import lru_cache
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Server Configuration
    server_port: int = Field(default=8081, env="MCP_SERVER_PORT")
    mcp_protocol_version: str = Field(default="2025-06-18", env="MCP_PROTOCOL_VERSION")
    
    # Security
    bearer_token: Optional[str] = Field(default=None, env="BEARER_TOKEN")
    
    # Google API Configuration
    google_client_id: Optional[str] = Field(default=None, env="GOOGLE_CLIENT_ID")
    google_client_secret: Optional[str] = Field(default=None, env="GOOGLE_CLIENT_SECRET")
    google_redirect_uri: Optional[str] = Field(default=None, env="GOOGLE_REDIRECT_URI")
    google_service_account_key_path: Optional[str] = Field(default=None, env="GOOGLE_SERVICE_ACCOUNT_KEY_PATH")
    google_oauth_token_secret: Optional[str] = Field(default=None, env="GOOGLE_OAUTH_TOKEN_SECRET")
    
    # Redis Configuration
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    
    # Observability
    otel_exporter_endpoint: Optional[str] = Field(default=None, env="OTEL_EXPORTER_OTLP_ENDPOINT")
    enable_telemetry: bool = Field(default=True, env="ENABLE_TELEMETRY")
    
    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    
    # Google Cloud Project (for Secret Manager)
    google_cloud_project: Optional[str] = Field(default=None, env="GOOGLE_CLOUD_PROJECT")
    
    # Rate Limiting
    max_requests_per_second: float = Field(default=10.0, env="MAX_REQUESTS_PER_SECOND")
    max_concurrent_requests: int = Field(default=50, env="MAX_CONCURRENT_REQUESTS")
    
    # Worker Configuration
    max_workers: int = Field(default=5, env="MAX_WORKERS")
    worker_queue_size: int = Field(default=100, env="WORKER_QUEUE_SIZE")
    
    # Retry Configuration
    max_retries: int = Field(default=3, env="MAX_RETRIES")
    retry_base_delay: float = Field(default=1.0, env="RETRY_BASE_DELAY")
    retry_max_delay: float = Field(default=60.0, env="RETRY_MAX_DELAY")
    
    # Development settings
    debug: bool = Field(default=False, env="DEBUG")
    development_mode: bool = Field(default=False, env="DEVELOPMENT_MODE")
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "extra": "ignore"
    }

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()

def validate_settings() -> tuple[bool, list[str]]:
    """
    Validate critical settings and return validation status
    
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    settings = get_settings()
    errors = []
    
    # Check for authentication configuration
    has_service_account = bool(settings.google_service_account_key_path)
    has_oauth = bool(settings.google_client_id and settings.google_client_secret)
    
    if not has_service_account and not has_oauth:
        errors.append(
            "No Google authentication configured. Set either "
            "GOOGLE_SERVICE_ACCOUNT_KEY_PATH or both GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET"
        )
    
    # Check OAuth configuration completeness
    if settings.google_client_id and not settings.google_client_secret:
        errors.append("GOOGLE_CLIENT_ID set but GOOGLE_CLIENT_SECRET missing")
    
    if settings.google_client_secret and not settings.google_client_id:
        errors.append("GOOGLE_CLIENT_SECRET set but GOOGLE_CLIENT_ID missing")
    
    # Validate port range
    if not (1 <= settings.server_port <= 65535):
        errors.append(f"Invalid server port: {settings.server_port}")
    
    # Validate log level
    valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if settings.log_level.upper() not in valid_log_levels:
        errors.append(f"Invalid log level: {settings.log_level}. Must be one of {valid_log_levels}")
    
    # Validate numeric settings
    if settings.max_requests_per_second <= 0:
        errors.append("MAX_REQUESTS_PER_SECOND must be positive")
    
    if settings.max_workers <= 0:
        errors.append("MAX_WORKERS must be positive")
    
    if settings.max_retries < 0:
        errors.append("MAX_RETRIES cannot be negative")
    
    return len(errors) == 0, errors

def get_environment_info() -> dict:
    """Get information about the current environment"""
    settings = get_settings()
    
    return {
        "server_port": settings.server_port,
        "mcp_protocol_version": settings.mcp_protocol_version,
        "log_level": settings.log_level,
        "debug_mode": settings.debug,
        "development_mode": settings.development_mode,
        "telemetry_enabled": settings.enable_telemetry,
        "has_service_account": bool(settings.google_service_account_key_path),
        "has_oauth_config": bool(settings.google_client_id and settings.google_client_secret),
        "redis_configured": settings.redis_url != "redis://localhost:6379/0",
        "worker_config": {
            "max_workers": settings.max_workers,
            "queue_size": settings.worker_queue_size,
            "max_requests_per_second": settings.max_requests_per_second
        }
    }
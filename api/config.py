"""
Configuration management for YouTube Contextual Product Pipeline API.
Loads environment variables and provides centralized config access.
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # OpenAI Configuration
    openai_api_key: str
    openai_model: str = "gpt-4o"
    openai_temperature: float = 0.7
    openai_max_tokens: int = 2000
    
    # YouTube Data API v3 Configuration
    youtube_api_key: str
    youtube_quota_limit: int = 10000
    
    # Database Configuration
    database_url: str = "sqlite:///./youtube_pipeline.db"
    
    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = True
    api_title: str = "YouTube Contextual Product Pipeline API"
    api_version: str = "1.0.0"
    api_description: str = "API for programmatic video campaign targeting"
    
    # Security
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # CORS
    cors_origins: list = [
        "http://localhost:8501",
        "http://localhost:3000",
        "http://localhost:5173",
    ]
    
    # Optional external integrations / runtime overrides
    streamlit_server_port: Optional[int] = None
    api_base_url: Optional[str] = None
    searchapi_key: Optional[str] = None
    vite_api_base_url: Optional[str] = None
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()

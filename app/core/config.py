import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""
    
    # Database
    mongodb_url: str
    database_name: str = "fastapi_auth_db"
    
    # JWT Settings
    jwt_secret_key: str = "your-super-secret-jwt-key-change-this-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Server
    server_host: str = "127.0.0.1"
    server_port: int = 8000
    
    # CORS
    cors_origins: list = ["*"]
    
    # OpenAI - Updated to supported model
    openai_api_key: str = "your-openai-api-key"
    openai_model: str = "gpt-4.1"  # Updated from deprecated gpt-4-vision-preview
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings() 
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings, loaded from environment variables."""
    
    # Server configuration
    port: int = Field(default=8000, env="PORT")
    debug_mode: bool = Field(default=False, env="DEBUG_MODE")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_dir: str = Field(default="logs", env="LOG_DIR")
    
    # Connection management
    max_reconnect_attempts: int = Field(default=5, env="MAX_RECONNECT_ATTEMPTS")
    reconnect_interval: int = Field(default=2, env="RECONNECT_INTERVAL")  # in seconds
    connection_timeout: int = Field(default=30, env="CONNECTION_TIMEOUT")  # in seconds
    ping_interval: int = Field(default=20, env="PING_INTERVAL")  # in seconds
    
    # WebRTC configuration
    webrtc_ice_servers: list = Field(
        default=[
            {"urls": ["stun:stun.l.google.com:19302"]}
        ],
        env="WEBRTC_ICE_SERVERS"
    )
    
    # Telemetry settings
    telemetry_buffer_size: int = Field(default=100, env="TELEMETRY_BUFFER_SIZE")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Create settings instance
settings = Settings()

# Ensure logs directory exists
os.makedirs(settings.log_dir, exist_ok=True) 
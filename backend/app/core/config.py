from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache
import os
from pathlib import Path



class Settings(BaseSettings):
    # App Config
    APP_NAME: str = "Riff Roulette"
    DEBUG: bool = True
    
    # Server Config
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # AWS Settings (also used by LocalStack)
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_DEFAULT_REGION: str = "us-east-1"
    BUCKET_NAME: str = "riff-roulette-models"
    
    # Model Paths (local development)
    MODEL_DIR: Path = Path("pretrained")
    ONSET_FRAMES_MODEL: str = "onset_frames/model.pt"
    MUSIC_VAE_MODEL: str = "music_vae/model.pt"
    DEMUCS_MODEL: str = "demucs/model.pt"
    
    # Audio Processing
    SAMPLE_RATE: int = 44100
    CHUNK_SIZE: int = 4096
    MAX_AUDIO_LENGTH: int = 30  # seconds
    
    # WebSocket
    WS_PING_INTERVAL: float = 20.0  # seconds
    WS_PING_TIMEOUT: float = 10.0
    
    # LocalStack
    USE_LOCALSTACK: bool = True
    LOCALSTACK_ENDPOINT: str = "http://localhost:4566"
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings"""
    return Settings()

# Helper function for model paths
def get_model_path(model_name: str) -> str:
    """Get full path to model file"""
    settings = get_settings()
    if settings.USE_LOCALSTACK:
        return os.path.join(settings.MODEL_DIR, model_name)
    else:
        return f"s3://{settings.BUCKET_NAME}/{model_name}"

# Initialize settings
settings = get_settings()
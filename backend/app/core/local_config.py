from pydantic_settings import BaseSettings
from pathlib import Path

class LocalConfig(BaseSettings):
    """Local development configuration"""
    pinata_api_key: str
    pinata_api_secret: str
    pinata_jwt: str
    pinata_index_cid: str
    # Base paths
    BASE_DIR: Path = Path(__file__).parent.parent.parent
    MODELS_DIR: Path = BASE_DIR / "pretrained"
    
    # Model paths
    DEMUCS_MODEL: Path = MODELS_DIR / "demucs/model.pt"
    MUSIC_VAE_MODEL: Path = MODELS_DIR / "music_vae/cat-mel_2bar_big.ckpt"
    ONSET_FRAMES_MODEL: Path = MODELS_DIR / "onset_frames/model.ckpt"
    
    # Server settings
    HOST: str = "localhost"
    PORT: int = 8000
    DEBUG: bool = True
    
    # WebSocket settings
    WS_PING_INTERVAL: int = 30  # seconds
    WS_PING_TIMEOUT: int = 10   # seconds
    
    class Config:
        env_file = ".env"

local_config = LocalConfig()
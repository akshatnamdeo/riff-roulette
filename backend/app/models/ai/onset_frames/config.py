from pydantic_settings import BaseSettings

class OnsetFramesConfig(BaseSettings):
    """Configuration for Onsets & Frames model with improved parameters"""
    hop_length: int = 512
    n_mels: int = 229
    sample_rate: int = 16000
    onset_threshold: float = 0.6  # Increased from 0.5
    frame_threshold: float = 0.4  # Increased from 0.3
    model_path: str = "pretrained/onset_frames/model.ckpt"
    
    # Guitar-specific settings
    fmin: float = 30.0  # Lowest guitar frequency (~B0)
    fmax: float = 8000.0  # Highest guitar frequency with harmonics
    
    # Note detection parameters
    min_note_duration: float = 0.05  # 50ms minimum
    max_note_duration: float = 5.0   # 5s maximum
    cluster_threshold: float = 0.03  # 30ms for clustering simultaneous notes
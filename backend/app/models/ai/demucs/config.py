from pydantic_settings import BaseSettings
from typing import List, Tuple
import torch

class DemucsConfig(BaseSettings):
    """Configuration for Demucs model"""
    # Audio processing
    sample_rate: int = 44100
    segment_size: int = 44100 * 10  # 10 seconds
    hop_length: int = 44100  # 1 second
    
    # Model architecture
    channels: int = 48
    growth: float = 2.0
    n_layers: int = 6
    kernel_size: int = 8
    stride: int = 4
    context: int = 3
    
    # Sources to separate
    sources: List[str] = ['drums', 'bass', 'guitar', 'vocals']
    
    # Model weights
    model_path: str = "pretrained/demucs/model.pt"
    
    # Real-time processing
    chunk_size: int = 16384  # Process in ~0.37s chunks at 44.1kHz
    transition_power: float = 1.0  # Smooth transition between chunks
    
    # STFT parameters
    n_fft: int = 4096
    win_length: int = 4096
    
    # Inference settings
    device: str = "cuda" if torch.cuda.is_available() else "cpu"
    num_workers: int = 2
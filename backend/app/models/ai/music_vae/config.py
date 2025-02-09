from pydantic_settings import BaseSettings
from typing import List

class MusicTransformerConfig(BaseSettings):
    """Configuration for Music Transformer model"""
    max_sequence_length: int = 1024
    n_layers: int = 6
    n_heads: int = 8
    d_model: int = 512
    d_ff: int = 2048
    dropout_rate: float = 0.1
    
    # Vocabulary settings
    vocab_size: int = 128  # MIDI note range
    max_velocity: int = 127
    time_steps: int = 100
    
    # Generation settings
    temperature: float = 1.0
    top_k: int = 0
    top_p: float = 0.9
    
    # Riff mutation settings
    mutation_rate: float = 0.3
    allowed_intervals: List[int] = [-12, -7, -5, -2, 0, 2, 5, 7, 12]  # Musical intervals
    model_path: str = "pretrained/music_vae/cat-mel_2bar_big.ckpt"

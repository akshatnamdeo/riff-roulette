from .demucs import DemucsModel, DemucsConfig, AudioSeparator
from .onset_frames import OnsetFramesModel, OnsetFramesConfig, AudioProcessor
from .music_vae import MusicTransformerModel, MusicTransformerConfig, RiffGenerator

__all__ = [
    'DemucsModel',
    'DemucsConfig',
    'AudioSeparator',
    'OnsetFramesModel',
    'OnsetFramesConfig',
    'AudioProcessor',
    'MusicTransformerModel',
    'MusicTransformerConfig',
    'RiffGenerator'
]
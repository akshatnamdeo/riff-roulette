from app.services.audio_processor import AudioProcessorService
from app.services.inference import InferenceService
from app.services.scoring import ScoringService
from app.services.websocket_manager import ConnectionManager
from app.core.local_config import local_config

from app.models.ai.demucs.config import DemucsConfig
from app.models.ai.music_vae.config import MusicTransformerConfig
from app.models.ai.onset_frames.config import OnsetFramesConfig

class ServiceContainer:
    """Container for managing service lifecycle"""
    
    def __init__(self):
        # Initialize configs with local paths
        self.demucs_config = DemucsConfig(
            model_path=str(local_config.DEMUCS_MODEL)
        )
        self.music_vae_config = MusicTransformerConfig(
            model_path=str(local_config.MUSIC_VAE_MODEL)
        )
        self.onset_frames_config = OnsetFramesConfig(
            model_path=str(local_config.ONSET_FRAMES_MODEL)
        )
        
        # Initialize services
        self.audio_processor = AudioProcessorService(
            demucs_config=self.demucs_config,
            onset_frames_config=self.onset_frames_config
        )
        
        self.inference_service = InferenceService(
            music_vae_config=self.music_vae_config
        )
        
        self.scoring_service = ScoringService()
        self.websocket_manager = ConnectionManager()
    
    async def initialize(self):
        """Initialize all services"""
        pass
    
    async def cleanup(self):
        """Cleanup all services"""
        if self.websocket_manager:
            self.websocket_manager.cleanup()
        if self.audio_processor:
            self.audio_processor.cleanup()
        if self.inference_service:
            self.inference_service.cleanup()
        if self.scoring_service:
            self.scoring_service.cleanup()
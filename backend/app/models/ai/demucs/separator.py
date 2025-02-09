import torch
import torch.nn.functional as F
import numpy as np
from typing import Dict, Optional, List
import soundfile as sf
from scipy import signal
from .config import DemucsConfig
from .model import DemucsModel
import resampy

class AudioSeparator:
    def __init__(self, config: DemucsConfig):
        self.config = config
        self.model = DemucsModel(config)

        if config.model_path:
            self.load_weights(config.model_path)

        self.model.to(config.device)
        self.model.eval()

    def load_weights(self, path: str):
        """Load pretrained weights"""
        checkpoint = torch.load(
            path, map_location='cpu', weights_only=False
        )
        if isinstance(checkpoint, dict):
            self.model.load_state_dict(checkpoint)
        elif isinstance(checkpoint, torch.jit.ScriptModule):
            # If the checkpoint is a TorchScript module,
            # assign it directly to self.model and attach a wrapper for separate_sources.
            self.model = checkpoint
            self.model.separate_sources = self._torchscript_separate_sources
        else:
            raise TypeError(
                f"Unsupported checkpoint type: {type(checkpoint)}. Expected dict or torch.jit.ScriptModule."
            )

    def _torchscript_separate_sources(
            self, mixture: torch.Tensor, chunk_size: Optional[int] = None
        ) -> torch.Tensor:
        """
        This wrapper replicates the original separate_sources logic for a TorchScript model.
        It uses the model's forward method to process chunks.
        """
        if chunk_size is None:
            chunk_size = self.config.chunk_size

        length = mixture.shape[-1]
        pad_length = int(np.ceil(length / chunk_size)) * chunk_size - length
        if pad_length > 0:
            mixture = F.pad(mixture, (0, pad_length))

        # Unfold the mixture into chunks.
        # mixture shape: [channels, length]
        # After unfold: [channels, n_chunks, chunk_size]
        chunks = mixture.unfold(-1, chunk_size, chunk_size)
        # Permute to get shape: [n_chunks, channels, chunk_size]
        chunks = chunks.permute(1, 0, 2)

        separated_chunks = []
        for chunk in chunks:
            with torch.no_grad():
                # Now, each chunk is [channels, chunk_size] (i.e. 2D) as required.
                separated = self.model.forward(chunk)
                separated_chunks.append(separated)

        # Concatenate the processed chunks along the time dimension (last dim)
        separated = torch.cat(separated_chunks, dim=-1)
        if pad_length > 0:
            separated = separated[..., :length]
        return separated

    def separate_stream(
        self,
        audio: np.ndarray,
        sample_rate: int,
        selected_sources: Optional[List[str]] = None
    ) -> Dict[str, np.ndarray]:
        # Resample if necessary
        if sample_rate != self.config.sample_rate:
            audio = self._resample(audio, sample_rate, self.config.sample_rate)

        # Convert to tensor
        audio_tensor = torch.from_numpy(audio).float().to(self.config.device)

        # Early return for silent input
        if torch.max(torch.abs(audio_tensor)) < 1e-6:
            time_samples = audio.shape[1]
            output = {}
            for source in self.config.sources:
                if selected_sources is None or source in selected_sources:
                    output[source] = np.zeros((audio.shape[0], time_samples))
            return output

        # Pad input to ensure output length matches input length (for model requirements)
        input_length = audio_tensor.shape[-1]
        pad_length = self.calculate_pad_length(input_length)
        if pad_length > 0:
            audio_tensor = F.pad(audio_tensor, (0, pad_length))

        # Process with model
        if hasattr(self.model, "separate_sources"):
            separated = self.model.separate_sources(audio_tensor)
        else:
            separated = self.model(audio_tensor)

        # Remove padding if added
        if pad_length > 0:
            separated = separated[..., :input_length]

        # Ensure the tensor has a batch dimension for interpolation
        if separated.dim() == 2:
            # Assuming shape is [channels, time], add batch dimension
            separated = separated.unsqueeze(0)

        # If the model output time dimension does not match the input length,
        # upsample the output to the original length.
        if separated.shape[-1] != input_length:
            separated = F.interpolate(
                separated, size=input_length, mode='linear', align_corners=False
            )

        # Remove the batch dimension if it was added
        if separated.shape[0] == 1:
            separated = separated.squeeze(0)

        # Convert to numpy and reshape to separate sources
        separated = separated.cpu().numpy()
        # Ensure output has the same number of channels as input
        num_channels = audio.shape[0]
        separated = separated.reshape(len(self.config.sources), num_channels, -1)

        # Create output dictionary
        if selected_sources is None:
            selected_sources = self.config.sources

        output = {}
        for idx, source in enumerate(self.config.sources):
            if source in selected_sources:
                output[source] = separated[idx]

        return output

    def calculate_pad_length(self, input_length: int) -> int:
        """
        Calculate the required padding to ensure the output length matches the input length.
        This depends on the model's architecture (e.g., stride and kernel size).
        """
        # Example: If the model halves the length at each layer, pad to the next multiple of 2^N
        # Adjust this logic based on your model's specific architecture.
        stride = 2  # Example stride value
        num_layers = self.config.n_layers  # Number of layers in the model
        target_length = input_length
        for _ in range(num_layers):
            target_length = (target_length + stride - 1) // stride
        for _ in range(num_layers):
            target_length *= stride
        pad_length = max(0, target_length - input_length)
        return pad_length
    def _resample(
        self,
        audio: np.ndarray,
        orig_sr: int,
        target_sr: int
    ) -> np.ndarray:
        """Resample audio to target sample rate"""
        if orig_sr == target_sr:
            return audio

        duration = audio.shape[1] / orig_sr
        new_length = int(duration * target_sr)

        resampled = []
        for channel in audio:
            resampled.append(
                signal.resample(channel, new_length)
            )

        return np.stack(resampled)

    def process_file(
        self,
        input_path: str,
        output_path: str,
        selected_sources: Optional[List[str]] = None
    ):
        """
        Process an audio file and save separated sources.
        """
        # Load audio file
        audio, sr = sf.read(input_path)
        if audio.ndim == 1:
            audio = np.stack([audio, audio])
        elif audio.shape[0] > 2:
            audio = audio.T

        # Separate sources
        separated = self.separate_stream(audio, sr, selected_sources)

        # Save each source
        for source_name, source_audio in separated.items():
            source_path = output_path.replace(
                '.wav',
                f'_{source_name}.wav'
            )
            sf.write(source_path, source_audio.T, sr)

    def isolate_guitar(
        self,
        audio: np.ndarray,
        sample_rate: int
    ) -> np.ndarray:
        """Isolate guitar track using Demucs model"""
        # Resample if needed
        if sample_rate != self.config.sample_rate:
            audio = resampy.resample(
                audio,
                sample_rate,
                self.config.sample_rate,
                axis=-1
            )
        
        # Ensure correct shape (channels, samples)
        if len(audio.shape) == 1:
            audio = np.stack([audio, audio])
        elif audio.shape[0] > 2:
            audio = audio.T
            
        # Convert to tensor
        audio_tensor = torch.from_numpy(audio).float().to(self.config.device)
        
        # Process through Demucs model
        with torch.no_grad():
            # Use the model's separation method
            separated = self.model.separate_sources(audio_tensor)
            
            # Get the guitar track (assuming it's in the expected position)
            guitar_idx = self.config.sources.index('guitar')
            guitar_audio = separated[guitar_idx].cpu().numpy()
        
        return guitar_audio
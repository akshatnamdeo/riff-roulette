import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import Dict, Optional, List
import soundfile as sf
import resampy
from .config import DemucsConfig

class DemucsModel(nn.Module):
    def __init__(self, config: DemucsConfig):
        super().__init__()
        self.config = config
        
        # Build layers
        self.encoder = nn.ModuleList()
        self.decoder = nn.ModuleList()
        
        channels = config.channels
        for index in range(config.n_layers):
            in_channels = channels * int(config.growth ** index)
            out_channels = channels * int(config.growth ** (index + 1))
            
            # Encoder layer
            self.encoder.append(
                DemucsLayer(
                    in_channels if index > 0 else 2,
                    out_channels,
                    config.kernel_size,
                    config.stride,
                    config.context
                )
            )
            
            # Decoder layer
            self.decoder.insert(
                0,
                DemucsLayer(
                    out_channels * 2,
                    in_channels if index > 0 else len(config.sources) * 2,
                    config.kernel_size,
                    config.stride,
                    config.context,
                    transpose=True
                )
            )

    def forward(self, mix: torch.Tensor) -> torch.Tensor:
        batch, channels, time = mix.size()
        
        # Apply encoder
        x = mix
        encoder_outputs = []
        for layer in self.encoder:
            x = layer(x)
            encoder_outputs.append(x)
        
        # Apply decoder with skip connections
        for layer, encoder_output in zip(self.decoder, reversed(encoder_outputs)):
            x = torch.cat([x, encoder_output], dim=1)
            x = layer(x)
        
        # Reshape output for sources
        x = x.view(batch, len(self.config.sources), channels, -1)
        return x

    @torch.jit.export
    def separate_sources(
        self,
        mixture: torch.Tensor,
        chunk_size: Optional[int] = None
    ) -> torch.Tensor:
        """Separate mixture into sources"""
        if chunk_size is None:
            chunk_size = self.config.chunk_size

        device = mixture.device
        batch_size = 1
        channels = mixture.shape[0]

        # Pad input if needed
        length = mixture.shape[-1]
        pad_length = int(np.ceil(length / chunk_size)) * chunk_size - length
        if pad_length > 0:
            mixture = F.pad(mixture, (0, pad_length))

        chunks = mixture.unfold(-1, chunk_size, chunk_size).transpose(0, -1)
        chunks = chunks.unsqueeze(1)  # Add batch dimension

        # Process chunks
        separated_chunks = []
        for chunk in chunks:
            with torch.no_grad():
                separated = self.forward(chunk)
                separated_chunks.append(separated)

        # Concatenate chunks
        separated = torch.cat(separated_chunks, dim=3)

        # Remove padding if added
        if pad_length > 0:
            separated = separated[..., :length]

        return separated

class DemucsLayer(nn.Module):
    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size: int,
        stride: int,
        context: int,
        transpose: bool = False,
        norm_groups: int = 4
    ):
        super().__init__()
        self.kernel_size = kernel_size
        self.stride = stride
        self.context = context
        self.transpose = transpose
        
        if transpose:
            self.conv = nn.ConvTranspose1d(
                in_channels, out_channels, kernel_size, stride)
        else:
            self.conv = nn.Conv1d(
                in_channels, out_channels, kernel_size, stride)
            
        self.norm = nn.GroupNorm(norm_groups, out_channels)
        self.relu = nn.ReLU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if self.context:
            if self.transpose:
                extra = self.context
                x = F.pad(x, (0, extra))
            else:
                padding = self.context
                x = F.pad(x, (padding, padding))
                
        out = self.conv(x)
        out = self.norm(out)
        out = self.relu(out)
        return out
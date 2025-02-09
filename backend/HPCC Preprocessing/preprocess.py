import asyncio
import io
import json
import time
import soundfile as sf
import numpy as np
from pathlib import Path
import pandas as pd
from tqdm import tqdm
import re
from typing import List, Dict, Any
import zlib
import base64

from app.services.audio_processor import AudioProcessorService
from app.models.schema import AudioChunk
from app.models.ai.onset_frames.config import OnsetFramesConfig
from app.models.ai.demucs.config import DemucsConfig

class NoteCompressor:
    @staticmethod
    def quantize_notes(notes: List[Dict[str, Any]], precision: int = 3) -> List[Dict[str, Any]]:
        """Quantize temporal values to reduce storage size."""
        return [{
            **note,
            'start': round(note['start'], precision),
            'end': round(note['end'], precision),
            'velocity': round(note['velocity'])
        } for note in notes]
    
    @staticmethod
    def delta_encode(notes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Store differences between successive values."""
        if not notes:
            return {'base': {}, 'deltas': []}
        
        base = notes[0].copy()
        deltas = []
        
        for i in range(1, len(notes)):
            delta = {
                'id': notes[i]['id'] - notes[i-1]['id'],
                'pitch': notes[i]['pitch'] - notes[i-1]['pitch'],
                'string': notes[i]['string'],  # Keep strings as is
                'velocity': notes[i]['velocity'] - notes[i-1]['velocity'],
                'start': round(notes[i]['start'] - notes[i-1]['start'], 3),
                'end': round(notes[i]['end'] - notes[i-1]['end'], 3)
            }
            deltas.append(delta)
        
        return {'base': base, 'deltas': deltas}
    
    @staticmethod
    def metadata_index(notes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Separate timing from note properties for efficient storage."""
        timings = [(note['start'], note['end']) for note in notes]
        properties = [{
            'id': note['id'],
            'pitch': note['pitch'],
            'string': note['string'],
            'velocity': note['velocity']
        } for note in notes]
        
        return {
            'timings': timings,
            'properties': properties
        }
    
    @staticmethod
    def compress_json(data: Any) -> str:
        """Compress any JSON-serializable data using zlib and base64 encode it."""
        json_str = json.dumps(data)
        compressed = zlib.compress(json_str.encode('utf-8'))
        return base64.b64encode(compressed).decode('utf-8')

async def generate_detected_notes(file_path: str, output_dir: Path, song_id: int, pbar: tqdm) -> List[Dict[str, Any]]:
    """Process audio file and generate note data with progress updates."""
    with open(file_path, "rb") as f:
        content = f.read()

    with io.BytesIO(content) as buf:
        audio, sr = sf.read(buf)

    # Truncate to first minute
    max_samples = sr * 60
    if len(audio) > max_samples:
        audio = audio[:max_samples]
        with io.BytesIO() as out_buf:
            sf.write(out_buf, audio, sr, format="WAV")
            truncated_bytes = out_buf.getvalue()
    else:
        truncated_bytes = content

    chunk = AudioChunk(
        data=truncated_bytes,
        sample_rate=sr,
        timestamp=time.time()
    )

    demucs_config = DemucsConfig(chunk_size=44100 * 30)
    onset_config = OnsetFramesConfig(
        onset_threshold=0.6,
        frame_threshold=0.4
    )

    processor = AudioProcessorService(
        demucs_config=demucs_config,
        onset_frames_config=onset_config
    )

    processed = await processor.process_audio_chunk(chunk)
    
    notes = [
        {
            "id": i,
            "pitch": note.pitch,
            "string": note.string,
            "velocity": note.velocity,
            "start": note.start,
            "end": note.end
        }
        for i, note in enumerate(processed.detected_notes)
    ]

    # Save different compressed versions
    compressor = NoteCompressor()
    base_path = output_dir / str(song_id)
    base_path.mkdir(exist_ok=True)
    
    # 1. Quantized version
    quantized = compressor.quantize_notes(notes)
    with open(base_path / "quantized.json.gz", "w") as f:
        f.write(compressor.compress_json(quantized))
    
    # 2. Delta encoded version
    delta_encoded = compressor.delta_encode(notes)
    with open(base_path / "delta.json.gz", "w") as f:
        f.write(compressor.compress_json(delta_encoded))
    
    # 3. Metadata indexed version
    indexed = compressor.metadata_index(notes)
    with open(base_path / "indexed.json.gz", "w") as f:
        f.write(compressor.compress_json(indexed))
    
    # 4. Original notes (compressed)
    with open(base_path / "original.json.gz", "w") as f:
        f.write(compressor.compress_json(notes))
    
    processor.cleanup()
    pbar.update(1)
    
    return notes

async def process_songs():
    # Setup directories
    base_dir = Path("HPCC Preprocessing")
    songs_dir = base_dir / "Songs"
    embeds_dir = base_dir / "Song Embeds"
    embeds_dir.mkdir(parents=True, exist_ok=True)
    
    # Get all MP3 files
    mp3_files = list(songs_dir.glob("*.mp3"))
    
    # Prepare song data for CSV
    song_data = []
    current_id = 101
    
    # Create progress bar
    with tqdm(total=len(mp3_files), desc="Processing songs", unit="song") as pbar:
        for mp3_file in mp3_files:
            # Parse filename
            match = re.match(r"(.+) - (.+)\.mp3", mp3_file.name)
            if not match:
                continue
                
            artist_name, song_name = match.groups()
            song_name = song_name.split(" (Remastered")[0]  # Remove remaster info
            
            # Process song and generate note data
            try:
                await generate_detected_notes(
                    str(mp3_file),
                    embeds_dir,
                    current_id,
                    pbar
                )
                
                song_data.append({
                    'song_id': current_id,
                    'artist_name': artist_name,
                    'song_name': song_name
                })
                
                current_id += 1
                
            except Exception as e:
                print(f"\nError processing {mp3_file.name}: {str(e)}")
    
    # Save song metadata to CSV
    df = pd.DataFrame(song_data)
    df.to_csv(base_dir / "song_data.csv", index=False)

if __name__ == "__main__":
    asyncio.run(process_songs())
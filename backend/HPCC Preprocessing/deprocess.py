import json
import zlib
import base64
from pathlib import Path
import pandas as pd
from typing import List, Dict, Any
from tqdm import tqdm

class NoteDecompressor:
    @staticmethod
    def decompress_data(compressed_str: str) -> Any:
        """Decompress base64+zlib compressed JSON data."""
        compressed_bytes = base64.b64decode(compressed_str)
        decompressed = zlib.decompress(compressed_bytes)
        return json.loads(decompressed.decode('utf-8'))
    
    @staticmethod
    def reconstruct_delta_notes(delta_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Reconstruct notes from delta encoding."""
        if not delta_data['deltas']:
            return [delta_data['base']] if delta_data['base'] else []
        
        notes = [delta_data['base']]
        prev = delta_data['base']
        
        for delta in delta_data['deltas']:
            current = {
                'id': prev['id'] + delta['id'],
                'pitch': prev['pitch'] + delta['pitch'],
                'string': delta['string'],
                'velocity': prev['velocity'] + delta['velocity'],
                'start': round(prev['start'] + delta['start'], 3),
                'end': round(prev['end'] + delta['end'], 3)
            }
            notes.append(current)
            prev = current
        
        return notes
    
    @staticmethod
    def reconstruct_indexed_notes(indexed_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Reconstruct notes from separated timing and properties."""
        notes = []
        for (start, end), props in zip(indexed_data['timings'], indexed_data['properties']):
            note = {
                **props,
                'start': start,
                'end': end
            }
            notes.append(note)
        return notes

def decompress_song(song_id: int, base_dir: Path, format_type: str = 'original') -> List[Dict[str, Any]]:
    """Decompress notes for a specific song ID and format."""
    song_dir = base_dir / "Song Embeds" / str(song_id)
    
    if not song_dir.exists():
        raise ValueError(f"No data found for song ID {song_id}")
    
    file_path = song_dir / f"{format_type}.json.gz"
    if not file_path.exists():
        raise ValueError(f"No {format_type} format found for song ID {song_id}")
    
    decompressor = NoteDecompressor()
    
    with open(file_path, 'r') as f:
        compressed_data = f.read()
    
    data = decompressor.decompress_data(compressed_data)
    
    if format_type == 'delta':
        return decompressor.reconstruct_delta_notes(data)
    elif format_type == 'indexed':
        return decompressor.reconstruct_indexed_notes(data)
    else:
        return data  # For 'original' and 'quantized' formats

def combine_songs(song_ids: List[int] = None, format_type: str = 'original') -> Dict[str, Any]:
    """Combine multiple songs' note data into a single structure."""
    base_dir = Path("HPCC Preprocessing")
    
    # Read song metadata
    try:
        df = pd.read_csv(base_dir / "song_data.csv")
    except FileNotFoundError:
        raise ValueError("song_data.csv not found")
    
    # If no song_ids provided, use all songs from the CSV
    if song_ids is None:
        song_ids = df['song_id'].tolist()
    
    combined_data = {}
    
    with tqdm(total=len(song_ids), desc=f"Decompressing {format_type} format") as pbar:
        for song_id in song_ids:
            try:
                # Get song metadata
                song_info = df[df['song_id'] == song_id].iloc[0]
                song_name = f"{song_info['artist_name']} - {song_info['song_name']}"
                
                # Decompress notes
                notes = decompress_song(song_id, base_dir, format_type)
                
                combined_data[song_name] = {
                    'song_id': int(song_id),
                    'artist': song_info['artist_name'],
                    'title': song_info['song_name'],
                    'notes': notes
                }
                
            except Exception as e:
                print(f"\nError processing song {song_id}: {str(e)}")
            
            pbar.update(1)
    
    return combined_data

if __name__ == "__main__":
    try:
        combined = combine_songs(format_type='original')
        
        # Save to a single JSON file
        output_path = Path("HPCC Preprocessing") / "combined_songs.json"
        with open(output_path, 'w') as f:
            json.dump(combined, f, indent=4)
        
        print(f"\nSuccessfully combined {len(combined)} songs into {output_path}")
        
    except Exception as e:
        print(f"Error: {str(e)}")
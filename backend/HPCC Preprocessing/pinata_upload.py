import requests
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import asyncio
import aiohttp
from datetime import datetime, timedelta
from tqdm import tqdm
from dotenv import load_dotenv

class PinataManager:
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://api.pinata.cloud"
        # Use API key authentication headers for all requests
        self.headers = {
            'pinata_api_key': api_key,
            'pinata_secret_api_key': api_secret
        }

    async def pin_file_to_ipfs(self, file_path: Path, metadata: Dict) -> Dict:
        """Pin a file to IPFS with metadata and customized pinning options."""
        url = f"{self.base_url}/pinning/pinFileToIPFS"
        
        # Customize pinning options
        pinataOptions = {
            "cidVersion": 1,
            "wrapWithDirectory": True,
            "customPinPolicy": {
                "regions": [
                    {"id": "FRA1", "desiredReplicationCount": 2},
                    {"id": "NYC1", "desiredReplicationCount": 2}
                ]
            }
        }
        
        timeout = aiohttp.ClientTimeout(total=30)  # 30-second timeout
        async with aiohttp.ClientSession(timeout=timeout) as session:
            with open(file_path, 'rb') as file:
                form = aiohttp.FormData()
                form.add_field('file', file)
                form.add_field('pinataOptions', json.dumps(pinataOptions))
                form.add_field('pinataMetadata', json.dumps(metadata))
                async with session.post(url, data=form, headers=self.headers) as response:
                    return await response.json()

    async def create_submarine_pin(self, cid: str, duration_hours: int = 24) -> Dict:
        """Create a submarine (temporary) pin."""
        url = f"{self.base_url}/pinning/createSubmarinePin"
        
        data = {
            "cid": cid,
            "timeoutInSeconds": duration_hours * 3600
        }
        
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=data, headers=self.headers) as response:
                return await response.json()

    async def pin_json_to_ipfs(self, json_data: Dict, metadata: Dict) -> Dict:
        """Pin JSON data to IPFS."""
        url = f"{self.base_url}/pinning/pinJSONToIPFS"
        
        data = {
            "pinataContent": json_data,
            "pinataMetadata": metadata,
            "pinataOptions": {
                "cidVersion": 1
            }
        }
        
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=data, headers=self.headers) as response:
                response_data = await response.json()
                if 'IpfsHash' not in response_data:
                    print("Full Pinata response:", response_data)
                    raise Exception("No IpfsHash in Pinata response")
                return response_data

    async def update_metadata(self, cid: str, metadata: Dict) -> Dict:
        """Update metadata for a pinned file."""
        url = f"{self.base_url}/pinning/hashMetadata"
        
        data = {
            "ipfsPinHash": cid,
            "name": metadata.get("name"),
            "keyvalues": metadata.get("keyvalues", {})
        }
        
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.put(url, json=data, headers=self.headers) as response:
                return await response.json()

class HPCCMusicUploader:
    def __init__(self, pinata: PinataManager, base_dir: Path):
        self.pinata = pinata
        self.base_dir = base_dir
        self.songs_dir = base_dir / "Songs"
        self.embeds_dir = base_dir / "Song Embeds"
        self.metadata_file = base_dir / "song_data.csv"

    def parse_song_filename(self, song_id: int) -> Tuple[str, str]:
        """Parse artist and title from the original song filename."""
        try:
            # Find the original mp3 file for this song ID
            song_files = list(self.songs_dir.glob("*.mp3"))
            if not song_files:
                return "Unknown Artist", "Unknown Title"

            # Get the corresponding file based on song_id order
            song_file = song_files[song_id - 101]  # Assuming IDs start at 101
            filename = song_file.stem  # Get filename without extension

            # Parse artist and title
            match = re.match(r"(.+) - (.+?)(?:\s*\(Remastered.*\))?$", filename)
            if match:
                artist, title = match.groups()
                return artist.strip(), title.strip()
            else:
                return "Unknown Artist", filename
        except Exception as e:
            print(f"Error parsing filename for song {song_id}: {e}")
            return "Unknown Artist", "Unknown Title"

    async def upload_song(self, song_id: int) -> Tuple[Dict, str, str]:
        """Upload all compression formats for a single song."""
        song_dir = self.embeds_dir / str(song_id)
        if not song_dir.exists():
            raise ValueError(f"No data found for song ID {song_id}")

        results = {}
        formats = ['original', 'quantized', 'delta', 'indexed']

        # Get artist and title for metadata
        artist, title = self.parse_song_filename(song_id)

        for format_type in formats:
            file_path = song_dir / f"{format_type}.json.gz"
            if not file_path.exists():
                continue

            metadata = {
                "name": f"song_{song_id}_{format_type}",
                "keyvalues": {
                    "songId": str(song_id),
                    "format": format_type,
                    "artist": artist,
                    "title": title,
                    "timestamp": datetime.now().isoformat(),
                    "compression": "gzip"
                }
            }

            try:
                result = await self.pinata.pin_file_to_ipfs(file_path, metadata)
                if 'IpfsHash' not in result:
                    print(f"Warning: Unexpected response for {format_type}:", result)
                    continue
                results[format_type] = result
                print(f"Successfully uploaded {format_type} for song {song_id}: {result['IpfsHash']}")
            except Exception as e:
                print(f"Error uploading {format_type} for song {song_id}: {str(e)}")
                continue

        return results, artist, title

    async def create_song_index(self, upload_data: List[Tuple[int, Dict, str, str]]) -> str:
        """Create and upload a master index of all songs."""
        index = {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "songs": {}
        }

        for song_id, formats, artist, title in upload_data:
            index["songs"][str(song_id)] = {
                "artist": artist,
                "title": title,
                "formats": {
                    format_type: data["IpfsHash"]
                    for format_type, data in formats.items()
                }
            }

        metadata = {
            "name": "hpcc_music_index",
            "keyvalues": {
                "version": "1.0",
                "type": "index",
                "created": datetime.now().isoformat()
            }
        }

        result = await self.pinata.pin_json_to_ipfs(index, metadata)
        return result["IpfsHash"]

async def main():
    load_dotenv()
    
    pinata = PinataManager(
        api_key=os.getenv('PINATA_API_KEY'),
        api_secret=os.getenv('PINATA_API_SECRET')
    )

    uploader = HPCCMusicUploader(
        pinata=pinata,
        base_dir=Path("HPCC Preprocessing")
    )

    # Upload all songs and track results
    upload_data = []  # List to store (song_id, formats, artist, title)
    song_ids = range(101, 151)  # Adjust range based on your data

    for song_id in tqdm(song_ids, desc="Uploading songs"):
        try:
            results, artist, title = await uploader.upload_song(song_id)
            upload_data.append((song_id, results, artist, title))
        except Exception as e:
            print(f"Error uploading song {song_id}: {str(e)}")

    # Create and upload index
    try:
        index_cid = await uploader.create_song_index(upload_data)
        print(f"\nIndex CID: {index_cid}")
        
        # Create a temporary submarine pin for testing
        submarine = await pinata.create_submarine_pin(index_cid, duration_hours=24)
        print(f"Submarine gateway URL: {submarine.get('gatewayURL')}")
        
    except Exception as e:
        print(f"Error creating index: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())

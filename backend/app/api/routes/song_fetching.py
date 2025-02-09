from fastapi import APIRouter, HTTPException
import aiohttp
import gzip
import json
from typing import Dict, List, Optional
import logging
import os
from dotenv import load_dotenv
import binascii
import base64

router = APIRouter()
logger = logging.getLogger(__name__)

# Configuration
load_dotenv()
PINATA_INDEX_CID = os.getenv('PINATA_INDEX_CID')
PINATA_GATEWAY = "https://gateway.pinata.cloud/ipfs"
PINATA_API_KEY = os.getenv('PINATA_API_KEY')
PINATA_API_SECRET = os.getenv('PINATA_API_SECRET')

async def fetch_pinata_data(cid: str) -> Dict:
    """
    Fetch JSON data from Pinata gateway (used for the index file).
    """
    url = f"{PINATA_GATEWAY}/{cid}"
    logger.info(f"Fetching from Pinata: {url}")
    headers = {
        'pinata_api_key': PINATA_API_KEY,
        'pinata_secret_api_key': PINATA_API_SECRET
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status != 200:
                raise HTTPException(status_code=response.status, detail="Failed to fetch from Pinata")
            data = await response.json()
            logger.info(f"Raw Pinata response: {data}")
            return data

async def fetch_pinata_raw(cid: str, file_name: Optional[str] = None) -> bytes:
    """
    Fetch raw bytes from Pinata gateway.
    Directly uses CID + filename path if filename is provided.
    """
    if file_name:
        url = f"{PINATA_GATEWAY}/{cid}/{file_name}"
    else:
        url = f"{PINATA_GATEWAY}/{cid}"
        
    logger.info(f"Fetching raw file from Pinata: {url}")
    headers = {
        'pinata_api_key': PINATA_API_KEY,
        'pinata_secret_api_key': PINATA_API_SECRET,
        'Accept': '*/*'
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status != 200:
                raise HTTPException(
                    status_code=response.status,
                    detail=f"Failed to fetch raw file from Pinata (Status: {response.status})"
                )
            raw = await response.read()
            logger.info(f"Fetched {len(raw)} bytes from {url}")
            return raw

def decompress_note_data(raw_data: bytes) -> List[Dict]:
    """
    Decompress note data.
    This function checks:
      - If the raw data is gzipped (magic bytes b'\x1f\x8b'), decompress using gzip.
      - Otherwise, try to decode as plain JSON.
      - If that fails (or the text does not start with '{' or '['), assume the data is
        a base64 encoded string of zlib-compressed JSON, decode it, then decompress using zlib.
    """
    try:
        logger.info(f"First 16 bytes (hex): {binascii.hexlify(raw_data[:16])}")
        # Check if gzipped
        if raw_data.startswith(b'\x1f\x8b'):
            logger.info("Data is gzipped, decompressing using gzip...")
            decompressed = gzip.decompress(raw_data)
            return json.loads(decompressed.decode('utf-8'))
        else:
            # Try to decode raw_data as UTF-8 text
            text = raw_data.decode('utf-8').strip()
            if text.startswith('{') or text.startswith('['):
                logger.info("Data is plain JSON, parsing directly...")
                return json.loads(text)
            else:
                logger.info("Data does not appear to be plain JSON. Assuming it is a base64 encoded string of zlib compressed data...")
                decoded = base64.b64decode(text)
                decompressed = __import__('zlib').decompress(decoded)
                return json.loads(decompressed.decode('utf-8'))
    except Exception as e:
        logger.error(f"Error decompressing note data: {str(e)}")
        logger.error(f"Raw data length: {len(raw_data)} bytes")
        raise HTTPException(status_code=500, detail="Failed to decompress note data")

@router.get("/songs")
async def list_songs():
    """Get list of available songs with metadata (id, artist, title)."""
    try:
        # Fetch and parse the index file from Pinata (JSON)
        index_data = await fetch_pinata_data(PINATA_INDEX_CID)
        logger.info(f"Parsed index data structure: {index_data}")
        
        # Extract and format song metadata (only id, artist, title)
        songs = []
        songs_data = index_data.get("songs", {})
        logger.info(f"Songs data from index: {songs_data}")

        for song_id, data in songs_data.items():
            song_info = {
                "id": int(song_id),
                "artist": data.get("artist", "Unknown Artist"),
                "title": data.get("title", "Unknown Title")
            }
            logger.debug(f"Processed song info: {song_info}")
            songs.append(song_info)
        
        sorted_songs = sorted(songs, key=lambda x: x["id"])
        logger.info(f"Final processed songs list: {sorted_songs}")
        
        return {
            "status": "success",
            "songs": sorted_songs
        }
    except Exception as e:
        logger.error(f"Error fetching song list: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/process-song/{song_id}")
async def process_song(song_id: int):
    """Process a specific song's note data."""
    try:
        # Fetch index data from Pinata
        index_data = await fetch_pinata_data(PINATA_INDEX_CID)
        logger.info(f"Processing song {song_id}")
        logger.debug(f"Index data structure: {index_data}")
        
        # Get song data from the index
        songs_data = index_data.get("songs", {})
        song_data = songs_data.get(str(song_id))
        if not song_data:
            logger.error(f"Song {song_id} not found in index")
            raise HTTPException(status_code=404, detail=f"Song {song_id} not found")
        
        logger.debug(f"Found song data: {song_data}")
        
        # Determine which format to use and the corresponding file name
        formats = song_data.get("formats", {})
        note_data_cid = None
        file_name = None
        if "original" in formats:
            note_data_cid = formats["original"]
            file_name = "original.json.gz"
        elif "quantized" in formats:
            note_data_cid = formats["quantized"]
            file_name = "quantized.json.gz"
        elif "delta" in formats:
            note_data_cid = formats["delta"]
            file_name = "delta.json.gz"
        elif "indexed" in formats:
            note_data_cid = formats["indexed"]
            file_name = "indexed.json.gz"
        
        if not note_data_cid:
            logger.error(f"No available note data found for song {song_id}")
            raise HTTPException(status_code=404, detail="Note data not found")
        
        logger.info(f"Fetching note data for CID: {note_data_cid} with file name: {file_name}")
        
        # Fetch the raw bytes of the note data file using the CID and file name
        raw_data = await fetch_pinata_raw(note_data_cid, file_name=file_name)
        
        # Decompress (or decode) the note data
        notes = decompress_note_data(raw_data)
        
        logger.info(f"Successfully decompressed {len(notes)} notes")
        logger.debug(f"Sample of notes data: {notes[:2] if notes else []}")
        
        # Format and return the response
        response_data = {
            "status": "success",
            "detected_notes": [
                {
                    "id": note["id"],
                    "pitch": note["pitch"],
                    "string": note["string"],
                    "velocity": note["velocity"],
                    "start": note["start"],
                    "end": note["end"],
                    "x": 800
                }
                for note in notes
            ],
            "sample_rate": 44100,
            "duration": max(note["end"] for note in notes) if notes else 0.0
        }
        
        return response_data
        
    except Exception as e:
        logger.error(f"Error processing song {song_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

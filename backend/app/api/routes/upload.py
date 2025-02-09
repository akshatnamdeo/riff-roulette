from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import soundfile as sf
import io
import time
import logging
import os
import json

from app.services.audio_processor import AudioProcessorService
from app.models.schema import AudioChunk, ProcessedAudio

router = APIRouter()
logger = logging.getLogger(__name__)
audio_processor = AudioProcessorService()

# Set devMode to True to load detected notes from a JSON file instead of reprocessing the MP3 file.
devMode = False

@router.post("/upload")
async def upload_audio(file: UploadFile = File(...)):
    """Handle audio file upload and initial processing"""
    try:
        if devMode:
            json_file_path = "detected_notes.json"
            if not os.path.exists(json_file_path):
                raise HTTPException(status_code=400, detail=f"Detected notes file '{json_file_path}' not found.")
            logger.info(f"DEV MODE: Loading detected notes from {json_file_path} instead of reprocessing MP3 file.")
            with open(json_file_path, "r") as f:
                detected_notes = json.load(f)
            # Optionally, define a default sample rate and calculate the duration from the detected notes.
            sample_rate = 44100
            if detected_notes:
                duration = max(note["end"] for note in detected_notes)
            else:
                duration = 0.0

            response_data = {
                "status": "success",
                "detected_notes": [
                    {
                        "id": i,
                        "pitch": note["pitch"],
                        "string": note["string"],
                        "velocity": note["velocity"],
                        "start": note["start"],
                        "end": note["end"],
                        "x": 800
                    }
                    for i, note in enumerate(detected_notes)
                ],
                "sample_rate": sample_rate,
                "duration": duration
            }
            logger.info(f"DEV MODE: Returning {len(detected_notes)} notes from JSON file.")
            return response_data
        else:
            logger.info(f"Receiving file upload: {file.filename}")
            content = await file.read()
            
            # Read audio file properties
            try:
                with io.BytesIO(content) as buf:
                    audio_data, sample_rate = sf.read(buf)
                    logger.info(f"Audio loaded successfully. Sample rate: {sample_rate}, Shape: {audio_data.shape}")
            except Exception as e:
                logger.error(f"Error reading audio file: {str(e)}")
                raise HTTPException(status_code=400, detail="Invalid audio file format")
                
            # Create audio chunk
            chunk = AudioChunk(
                data=content,
                sample_rate=sample_rate,
                timestamp=time.time()
            )
            
            # Process audio
            logger.info("Starting audio processing...")
            processed: ProcessedAudio = await audio_processor.process_audio_chunk(chunk)
            logger.info(f"Audio processed. Found {len(processed.detected_notes)} notes")
            
            # Log each detected note for debugging
            for i, note in enumerate(processed.detected_notes):
                logger.debug(
                    f"Note {i}: pitch={note.pitch}, "
                    f"string={note.string}, "
                    f"start={note.start:.3f}, "
                    f"end={note.end:.3f}"
                )
            
            response_data = {
                "status": "success",
                "detected_notes": [
                    {
                        "id": i,
                        "pitch": note.pitch,
                        "string": note.string,
                        "velocity": note.velocity,
                        "start": note.start,
                        "end": note.end,
                        "x": 800  # Start position for frontend
                    }
                    for i, note in enumerate(processed.detected_notes)
                ],
                "sample_rate": processed.sample_rate,
                "duration": processed.duration
            }
            
            logger.info(f"Upload successful. Returning {len(processed.detected_notes)} notes")
            return response_data
    except Exception as e:
        logger.error(f"Upload error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))

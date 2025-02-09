import numpy as np
from typing import Tuple, Optional, List
import io
import soundfile as sf
from app.models.schema import GuitarString, ProcessedAudio, AudioChunk, NoteEvent
from app.models.ai.demucs.separator import AudioSeparator
from app.models.ai.demucs.config import DemucsConfig
from app.models.ai.onset_frames.model import OnsetFramesModel, AudioProcessor as OnsetFramesProcessor
from app.models.ai.onset_frames.config import OnsetFramesConfig
import resampy
import asyncio
from concurrent.futures import ThreadPoolExecutor
import math
import logging

logger = logging.getLogger(__name__)

class AudioProcessorService:
    def __init__(
        self,
        demucs_config: Optional[DemucsConfig] = None,
        onset_frames_config: Optional[OnsetFramesConfig] = None
    ):
        """Initialize the audio processing service with AI models"""
        self.demucs_config = demucs_config or DemucsConfig(chunk_size=44100 * 30)
        self.onset_frames_config = onset_frames_config or OnsetFramesConfig(
            onset_threshold=0.6,
            frame_threshold=0.4
        )
        # Initialize AI models
        self.separator = AudioSeparator(self.demucs_config)
        self.onset_frames = OnsetFramesModel(self.onset_frames_config)
        self.onset_processor = OnsetFramesProcessor(self.onset_frames_config)
        
        # Thread pool for CPU-intensive processing
        self.executor = ThreadPoolExecutor(max_workers=2)

    async def _process_in_threadpool(
        self,
        audio: np.ndarray,
        sample_rate: int
    ) -> Tuple[np.ndarray, list]:
        """Process audio with proper streaming support"""
        loop = asyncio.get_event_loop()
        logger.debug(f"Input audio shape: {audio.shape}")

        # First isolate guitar track
        isolation_task = loop.run_in_executor(
            self.executor,
            self._isolate_guitar,
            audio,
            sample_rate
        )
        
        isolated_guitar = await isolation_task
        logger.debug(f"Isolated guitar shape: {isolated_guitar.shape}")

        # Process in overlapping chunks
        CHUNK_DURATION = 12.0  # seconds
        OVERLAP = 2.0  # seconds
        
        chunk_samples = int(CHUNK_DURATION * self.onset_frames_config.sample_rate)
        overlap_samples = int(OVERLAP * self.onset_frames_config.sample_rate)
        hop_samples = chunk_samples - overlap_samples
        
        # Resample isolated guitar if needed
        if self.demucs_config.sample_rate != self.onset_frames_config.sample_rate:
            isolated_guitar = resampy.resample(
                isolated_guitar,
                self.demucs_config.sample_rate,
                self.onset_frames_config.sample_rate,
                axis=-1
            )
        
        # Convert to mono if needed
        if len(isolated_guitar.shape) > 1:
            isolated_guitar = np.mean(isolated_guitar, axis=0)
            
        # Calculate number of chunks
        total_samples = len(isolated_guitar)
        num_chunks = math.ceil((total_samples - overlap_samples) / hop_samples)
        logger.debug(f"Processing {num_chunks} chunks of {CHUNK_DURATION}s with {OVERLAP}s overlap")
        
        all_notes = []
        
        for i in range(num_chunks):
            start_idx = i * hop_samples
            end_idx = min(start_idx + chunk_samples, total_samples)
            
            chunk = isolated_guitar[start_idx:end_idx]
            
            # Ensure chunk is the right length
            if len(chunk) < chunk_samples:
                chunk = np.pad(chunk, (0, chunk_samples - len(chunk)))
            
            # Detect notes in chunk
            chunk_notes = await loop.run_in_executor(
                self.executor,
                self._detect_notes_in_chunk,
                chunk,
                start_idx / self.onset_frames_config.sample_rate
            )
            
            # Filter notes in overlap region
            if i < num_chunks - 1:
                chunk_notes = [
                    note for note in chunk_notes
                    if note.start < ((i + 1) * (CHUNK_DURATION - OVERLAP))
                ]
            
            logger.debug(f"Chunk {i+1}/{num_chunks}: {len(chunk_notes)} notes from {start_idx/self.onset_frames_config.sample_rate:.2f}s to {end_idx/self.onset_frames_config.sample_rate:.2f}s")
            all_notes.extend(chunk_notes)
        
        logger.debug(f"Total notes detected: {len(all_notes)}")
        return isolated_guitar, all_notes
    
    def _detect_notes_in_chunk(
        self,
        audio_chunk: np.ndarray,
        time_offset: float
    ) -> List[NoteEvent]:
        """Process a single chunk of audio"""
        # Prepare mel spectrogram
        mel_spec = self.onset_processor.preprocess_audio(audio_chunk)
        
        # Get model predictions
        onset_probs, frame_probs = self.onset_frames.predict(mel_spec)
        
        # Process predictions
        raw_notes = self.onset_processor.process_predictions(
            onset_probs[0],
            frame_probs[0],
            min_duration=0.05
        )
        
        # Adjust note timestamps
        for note in raw_notes:
            note['start'] += time_offset
            note['end'] += time_offset
        
        # Post-process notes
        processed_notes = self._post_process_notes(raw_notes)
        
        return [
            NoteEvent(
                pitch=note['pitch'],
                velocity=note['velocity'],
                start=note['start'],
                end=note['end'],
                string=self._determine_string(note['pitch'])
            )
            for note in processed_notes
        ]

    def _post_process_notes(self, raw_notes: List[dict]) -> List[dict]:
        """Post-process detected notes with improved filtering for playability"""
        if not raw_notes:
            return []

        # First assign strings to all notes
        for note in raw_notes:
            note['string'] = self._determine_string(note['pitch'])

        # Sort notes by start time and pitch
        notes = sorted(raw_notes, key=lambda x: (x['start'], x['pitch']))
        
        # Parameters for playability
        MIN_DURATION = 0.1    # Minimum note duration in seconds (100ms)
        MAX_DURATION = 2.0    # Maximum note duration in seconds
        MIN_VELOCITY = 50     # Higher velocity threshold for clearer notes
        MIN_GAP_PER_STRING = 0.25  # Minimum 250ms between notes on same string
        MAX_SIMULTANEOUS = 4  # Max 4 notes in a chord
        MAX_NOTES_PER_WINDOW = 3  # Maximum notes in a 1-second window per string
        
        # First pass: Basic filtering
        filtered_notes = [
            note for note in notes
            if (note['end'] - note['start']) >= MIN_DURATION
            and (note['end'] - note['start']) <= MAX_DURATION
            and note['velocity'] >= MIN_VELOCITY
        ]
        
        # Second pass: Limit notes per second per string
        string_notes = {}
        for string in GuitarString:
            string_notes[string] = []
            
        for note in filtered_notes:
            string_notes[note['string']].append(note)
            
        rate_limited_notes = []
        for string, notes_list in string_notes.items():
            # Sort by start time
            notes_list.sort(key=lambda x: x['start'])
            
            # Sliding window to limit note density
            window_notes = []
            for note in notes_list:
                # Remove notes that are outside the 1-second window
                window_start = note['start'] - 1.0
                window_notes = [n for n in window_notes if n['start'] > window_start]
                
                # Only add note if we haven't exceeded our limit
                if len(window_notes) < MAX_NOTES_PER_WINDOW:
                    window_notes.append(note)
                    rate_limited_notes.append(note)
        
        # Sort back by overall timing
        filtered_notes = sorted(rate_limited_notes, key=lambda x: x['start'])
        
        # Third pass: Handle chords and overlaps
        playable_notes = []
        current_chord = []
        current_chord_time = 0
        
        for note in filtered_notes:
            # Start new chord if needed
            if note['start'] - current_chord_time > MIN_GAP_PER_STRING:
                if current_chord:
                    playable_notes.extend(self._adjust_chord_timing(current_chord))
                current_chord = []
                current_chord_time = note['start']
            
            # Add to current chord if possible
            if len(current_chord) < MAX_SIMULTANEOUS and \
               all(n['string'] != note['string'] for n in current_chord):
                current_chord.append(note)
            else:
                # Add as regular note
                if current_chord:
                    playable_notes.extend(self._adjust_chord_timing(current_chord))
                    current_chord = []
                playable_notes.append(note)
        
        # Add any remaining chord notes
        if current_chord:
            playable_notes.extend(self._adjust_chord_timing(current_chord))
        
        return playable_notes

    def _adjust_chord_timing(self, chord_notes: List[dict]) -> List[dict]:
        """Adjust timing of notes in a chord for better playability"""
        if not chord_notes:
            return []
            
        # Sort by pitch to ensure consistent ordering
        chord_notes.sort(key=lambda x: x['pitch'])
        
        # Make all chord notes have same duration
        avg_duration = sum(n['end'] - n['start'] for n in chord_notes) / len(chord_notes)
        start_time = min(n['start'] for n in chord_notes)
        
        # Spread notes slightly (1ms apart) for more natural sound
        TIME_SPREAD = 0.001
        for i, note in enumerate(chord_notes):
            note['start'] = start_time + (i * TIME_SPREAD)
            note['end'] = note['start'] + avg_duration
            
        return chord_notes

    def _determine_string(self, pitch: int) -> GuitarString:
        """Map MIDI pitch to guitar string with more accurate ranges"""
        if pitch < 40: return GuitarString.LOW_E    # Low E (E2)
        if pitch < 45: return GuitarString.A        # A2
        if pitch < 50: return GuitarString.D        # D3
        if pitch < 55: return GuitarString.G        # G3
        if pitch < 59: return GuitarString.B        # B3
        return GuitarString.HIGH_E                  # E4 and above

    async def process_audio_chunk(self, chunk: AudioChunk) -> ProcessedAudio:
        """Process an audio chunk through the AI pipeline"""
        try:
            logger.debug("Processing audio chunk")
            audio_data = self._bytes_to_audio(chunk.data, chunk.sample_rate)
            
            # Process in thread pool to avoid blocking
            isolated_guitar, detected_notes = await self._process_in_threadpool(
                audio_data,
                chunk.sample_rate
            )
            
            logger.debug(f"Detected {len(detected_notes)} notes")
            for note in detected_notes:
                logger.debug(f"Note: pitch={note.pitch}, string={note.string}, start={note.start:.3f}")
            
            # Convert processed audio back to bytes
            output_bytes = self._audio_to_bytes(
                isolated_guitar,
                self.demucs_config.sample_rate
            )
            
            return ProcessedAudio(
                isolated_guitar=output_bytes,
                detected_notes=detected_notes,
                sample_rate=self.demucs_config.sample_rate,
                duration=len(isolated_guitar) / self.demucs_config.sample_rate if len(isolated_guitar.shape) == 1 else len(isolated_guitar[0]) / self.demucs_config.sample_rate,
                timestamp=chunk.timestamp
            )
            
        except Exception as e:
            logger.error(f"Error processing audio chunk: {str(e)}", exc_info=True)
            raise RuntimeError(f"Error processing audio chunk: {str(e)}")

    def _bytes_to_audio(
        self,
        audio_bytes: bytes,
        sample_rate: int
    ) -> np.ndarray:
        """Convert audio bytes to numpy array"""
        with io.BytesIO(audio_bytes) as buf:
            audio, _ = sf.read(buf)
            # Ensure correct shape (channels, samples)
            if len(audio.shape) == 1:
                audio = np.stack([audio, audio])
            elif audio.shape[0] > 2:
                audio = audio.T
        return audio

    def _isolate_guitar(
        self,
        audio: np.ndarray,
        sample_rate: int
    ) -> np.ndarray:
        """Isolate guitar track using Demucs"""
        # Resample if needed
        if sample_rate != self.demucs_config.sample_rate:
            audio = resampy.resample(
                audio,
                sample_rate,
                self.demucs_config.sample_rate,
                axis=-1
            )
        
        # Ensure correct shape (channels, samples)
        if len(audio.shape) == 1:
            audio = np.stack([audio, audio])
        elif audio.shape[0] > 2:
            audio = audio.T
            
        # Process through Demucs
        isolated = self.separator.isolate_guitar(
            audio,
            self.demucs_config.sample_rate
        )
        
        return isolated

    def _audio_to_bytes(
        self,
        audio: np.ndarray,
        sample_rate: int
    ) -> bytes:
        """Convert numpy array to audio bytes"""
        with io.BytesIO() as buf:
            # Ensure correct shape for writing
            if len(audio.shape) > 1:
                audio = audio.T
            sf.write(buf, audio, sample_rate, format='WAV')
            return buf.getvalue()

    def cleanup(self):
        """Cleanup resources"""
        self.executor.shutdown(wait=True)
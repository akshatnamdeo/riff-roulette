from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Union
from enum import Enum
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class GuitarString(str, Enum):
    """Guitar strings enumeration"""
    LOW_E = "E"
    A = "A"
    D = "D"
    G = "G"
    B = "B"
    HIGH_E = "e"

class MessageType(str, Enum):
    """Types of WebSocket messages"""
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    AUDIO_CHUNK = "audio_chunk"
    RIFF_MUTATION = "riff_mutation"
    SCORE_UPDATE = "score_update"
    PROBLEM_START = "problem_start"
    PROBLEM_END = "problem_end"
    NOTE_HIT = "note_hit"
    ERROR = "error"
    SESSION_STATE = "session_state"
    NOTE_MISS = "note_miss"
    PAUSE_GAME = "pause_game"
    RESUME_GAME = "resume_game"
    PROBLEM_WARNING = "problem_warning"
    SESSION_END = "session_end"
    END_GAME = "end_game"

class NoteEvent(BaseModel):
    """Individual note event detected from audio"""
    id: Optional[int] = None
    pitch: int = Field(..., ge=0, le=127)  # MIDI note number
    velocity: int = Field(..., ge=0, le=127)
    start: float  # Time in seconds
    end: float
    string: GuitarString  # Guitar string this note belongs to
    x: Optional[float] = None  # Position for frontend visualization
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)

    @classmethod
    def from_pitch(cls, pitch: int, start: float, end: float, velocity: int = 64):
        """Create a note event from a pitch value, automatically determining the string"""
        string = GuitarString.LOW_E
        if pitch < 40: string = GuitarString.LOW_E
        elif pitch < 45: string = GuitarString.A
        elif pitch < 50: string = GuitarString.D
        elif pitch < 55: string = GuitarString.G
        elif pitch < 59: string = GuitarString.B
        else: string = GuitarString.HIGH_E
        
        return cls(
            pitch=pitch,
            velocity=velocity,
            start=start,
            end=end,
            string=string
        )

    class Config:
        arbitrary_types_allowed = True

class AudioChunk(BaseModel):
    """Chunk of audio data for processing"""
    data: bytes
    sample_rate: int
    timestamp: float

    class Config:
        arbitrary_types_allowed = True

class ProcessedAudio(BaseModel):
    """Processed audio with extracted features"""
    isolated_guitar: bytes
    detected_notes: List[NoteEvent]
    sample_rate: int
    duration: float
    timestamp: float

    class Config:
        arbitrary_types_allowed = True

class RiffMutation(BaseModel):
    """AI-generated mutation of a riff"""
    original_notes: List[NoteEvent]
    mutated_notes: List[NoteEvent]
    mutation_type: str
    problem_duration: float = 5.0  # Duration of problem section in seconds
    timestamp: float = Field(default_factory=lambda: datetime.now().timestamp())

class MutationRequest(BaseModel):
    """Request for an AI mutation of a riff"""
    notes: List[NoteEvent]
    mutation_strength: float = Field(0.5, ge=0.0, le=1.0)
    preserve_rhythm: bool = True
    performance_state: Optional[Dict[str, float]] = None

class MutationResponse(BaseModel):
    """Response containing the mutated riff"""
    original_notes: List[NoteEvent]
    mutated_notes: List[NoteEvent]
    mutation_type: str
    confidence: float
    processing_time: float
    problem_duration: float = 5.0

class ScoreComponent(BaseModel):
    """Individual component of the player's score"""
    category: str  # "creativity", "reaction", "rhythm"
    value: float
    weight: float = 1.0
    timestamp: float = Field(default_factory=lambda: datetime.now().timestamp())

class ScoreUpdate(BaseModel):
    """Update to the player's score"""
    components: List[ScoreComponent]
    total_score: float
    combo_multiplier: float = 1.0
    timestamp: float = Field(default_factory=lambda: datetime.now().timestamp())

class NoteHitEvent(BaseModel):
    """Event when player hits a note"""
    note_id: int
    string: GuitarString
    hit_time: float
    accuracy: float = Field(..., ge=-1.0, le=1.0)  # -1.0 (early) to 1.0 (late)

class GameState(BaseModel):
    """Current state of a gameplay session"""
    mode: str = "normal"  # "normal" or "problem"
    current_notes: List[Union[Dict, NoteEvent]] = Field(default_factory=list)  # Allow both Dict and NoteEvent
    problem_section: Optional[RiffMutation] = None
    score: float = 0.0
    combo: int = 0
    difficulty_level: str = "medium"
    last_hit_time: Optional[float] = None
    is_active: bool = True
    is_paused: bool = False
    mutation_strength: float = 0.5
    
    @property
    def serialize(self):
        return {
            "mode": self.mode,
            "current_notes": [
                note.dict() if isinstance(note, NoteEvent) else note 
                for note in self.current_notes
            ],
            "problem_section": self.problem_section.dict() if self.problem_section else None,
            "score": self.score,
            "combo": self.combo,
            "difficulty_level": self.difficulty_level,
            "last_hit_time": self.last_hit_time,
            "is_active": self.is_active,
            "is_paused": self.is_paused,
            "mutation_strength": self.mutation_strength
        }

    class Config:
        arbitrary_types_allowed = True

class WebSocketMessage(BaseModel):
    """Container for all WebSocket messages"""
    type: MessageType
    payload: Union[
        AudioChunk,
        RiffMutation,
        ScoreUpdate,
        GameState,
        NoteHitEvent,
        Dict
    ]
    timestamp: float = Field(default_factory=lambda: datetime.now().timestamp())

class ScoreMetrics(BaseModel):
    """Detailed scoring metrics for a session"""
    creativity_score: float = Field(0.0, ge=0.0, le=100.0)
    reaction_score: float = Field(0.0, ge=0.0, le=100.0)
    rhythm_score: float = Field(0.0, ge=0.0, le=100.0)
    combo_multiplier: float = Field(1.0, ge=1.0)
    total_score: float = 0.0

class SessionState(BaseModel):
    """Current state of a gameplay session"""
    start_time: datetime
    current_score: float = 0.0
    riff_count: int = 0
    last_mutation_time: Optional[float] = None
    is_active: bool = True
    difficulty_level: str = "medium"

class ErrorMessage(BaseModel):
    """Error message for WebSocket communication"""
    code: str
    message: str
    details: Optional[Dict] = None
    timestamp: float
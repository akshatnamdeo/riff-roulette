import asyncio
from typing import List, Optional, Dict
import time
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from app.models.schema import (
    NoteEvent,
    MutationRequest,
    MutationResponse,
    RiffMutation,
    GuitarString
)
from app.models.ai.music_vae.model import RiffGenerator
from app.models.ai.music_vae.config import MusicTransformerConfig
from app.services.adaptive_mutation import AdaptiveMutationService

class InferenceService:
    def __init__(
        self,
        music_vae_config: Optional[MusicTransformerConfig] = None,
        max_workers: int = 2
    ):
        self.config = music_vae_config or MusicTransformerConfig()
        self.riff_generator = RiffGenerator(self.config)
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.mutation_cache = {}
        self.cache_size = 100
        self.adaptive_mutation = AdaptiveMutationService()

    async def generate_mutation(
        self,
        request: MutationRequest
    ) -> MutationResponse:
        """Generate a mutation of the input riff using the AI model"""
        try:
            start_time = time.time()
            
            # Check cache
            cache_key = self._generate_cache_key(request.notes)
            if cache_key in self.mutation_cache:
                cached = self.mutation_cache[cache_key]
                if (cached['mutation_strength'] == request.mutation_strength and
                    cached['preserve_rhythm'] == request.preserve_rhythm):
                    return cached['response']
            
            # Get performance state for adaptive mutation
            performance_state = request.performance_state or {
                'creativity': 70.0,
                'reaction': 70.0,
                'rhythm': 70.0
            }
            
            # Process mutation in thread pool
            loop = asyncio.get_event_loop()
            mutated_notes = await loop.run_in_executor(
                self.executor,
                self._mutate_notes,
                request.notes,
                request.mutation_strength,
                request.preserve_rhythm,
                performance_state
            )
            
            # Analyze mutation characteristics
            mutation_type = self._analyze_mutation_type(request.notes, mutated_notes)
            confidence = self._calculate_mutation_confidence(request.notes, mutated_notes)
            
            response = MutationResponse(
                original_notes=request.notes,
                mutated_notes=mutated_notes,
                mutation_type=mutation_type,
                confidence=confidence,
                processing_time=time.time() - start_time,
                problem_duration=5.0  # Default problem section duration
            )
            
            # Update cache
            self._update_cache(cache_key, {
                'mutation_strength': request.mutation_strength,
                'preserve_rhythm': request.preserve_rhythm,
                'response': response
            })
            
            return response
            
        except Exception as e:
            raise RuntimeError(f"Error generating mutation: {str(e)}")

    def _mutate_notes(
        self,
        notes: List[NoteEvent],
        mutation_strength: float,
        preserve_rhythm: bool,
        performance_state: Dict[str, float]
    ) -> List[NoteEvent]:
        """Apply AI mutation to the notes"""
        # Convert performance state to RL state vector
        state = np.array([
            performance_state.get('creativity', 70.0),
            performance_state.get('reaction', 70.0),
            performance_state.get('rhythm', 70.0)
        ])
        
        # Adjust mutation strength using RL agent
        adjusted_strength = self.adaptive_mutation.adjust_mutation_strength(
            mutation_strength,
            state
        )
        
        # Prepare notes for mutation
        note_dicts = [
            {
                'pitch': note.pitch,
                'velocity': note.velocity,
                'start': note.start,
                'end': note.end,
                'string': note.string
            }
            for note in notes
        ]

        # Apply mutation
        original_rate = self.config.mutation_rate
        self.config.mutation_rate = adjusted_strength

        try:
            mutated_dicts = self.riff_generator.mutate_riff(note_dicts)
            
            if preserve_rhythm:
                mutated_dicts = self._preserve_note_timing(note_dicts, mutated_dicts)
            
            # Convert back to NoteEvents with proper string assignment
            return [
                NoteEvent(
                    pitch=note['pitch'],
                    velocity=note['velocity'],
                    start=note['start'],
                    end=note['end'],
                    string=GuitarString(self._determine_string(note['pitch']))
                )
                for note in mutated_dicts
            ]
        finally:
            self.config.mutation_rate = original_rate

    def _determine_string(self, pitch: int) -> str:
        """Determine which guitar string a pitch belongs to"""
        if pitch < 40: return "E"    # Low E
        if pitch < 45: return "A"
        if pitch < 50: return "D"
        if pitch < 55: return "G"
        if pitch < 59: return "B"
        return "e"                   # High E

    def _preserve_note_timing(
        self,
        original: List[dict],
        mutated: List[dict]
    ) -> List[dict]:
        """Preserve the rhythm while keeping mutated pitches"""
        if len(original) != len(mutated):
            return self._interpolate_timing(original, mutated)
            
        preserved = []
        for orig, mut in zip(original, mutated):
            preserved.append({
                'pitch': mut['pitch'],
                'velocity': mut['velocity'],
                'start': orig['start'],
                'end': orig['end'],
                'string': self._determine_string(mut['pitch'])
            })
        return preserved

    def _interpolate_timing(
        self,
        original: List[dict],
        mutated: List[dict]
    ) -> List[dict]:
        """Interpolate timing when note counts don't match"""
        orig_duration = original[-1]['end'] - original[0]['start']
        mut_duration = mutated[-1]['end'] - mutated[0]['start']
        scale = orig_duration / mut_duration
        
        return [{
            'pitch': note['pitch'],
            'velocity': note['velocity'],
            'start': note['start'] * scale,
            'end': note['end'] * scale,
            'string': self._determine_string(note['pitch'])
        } for note in mutated]

    def _analyze_mutation_type(
        self,
        original: List[NoteEvent],
        mutated: List[NoteEvent]
    ) -> str:
        """Determine the primary type of mutation that occurred"""
        changes = {
            'pitch': 0,
            'rhythm': 0,
            'velocity': 0
        }
        
        for orig, mut in zip(original, mutated):
            if orig.pitch != mut.pitch:
                changes['pitch'] += 1
            if abs(orig.end - orig.start - (mut.end - mut.start)) > 0.01:
                changes['rhythm'] += 1
            if abs(orig.velocity - mut.velocity) > 5:
                changes['velocity'] += 1
                
        return max(changes.items(), key=lambda x: x[1])[0]

    def _calculate_mutation_confidence(
        self,
        original: List[NoteEvent],
        mutated: List[NoteEvent]
    ) -> float:
        """Calculate confidence score for the mutation"""
        confidence = 1.0
        
        for orig, mut in zip(original, mutated):
            # Check pitch changes
            pitch_diff = abs(orig.pitch - mut.pitch)
            if pitch_diff > 12:  # More than an octave
                confidence *= 0.9
                
            # Check velocity changes
            if abs(orig.velocity - mut.velocity) > 40:
                confidence *= 0.95
                
            # Check string changes
            if orig.string != mut.string:
                confidence *= 0.95
                
        # Check overall structure
        if len(mutated) != len(original):
            confidence *= 0.9
            
        # Check pitch range
        pitches = [n.pitch for n in mutated]
        if max(pitches) - min(pitches) > 24:  # More than 2 octaves
            confidence *= 0.9
            
        return max(0.1, min(confidence, 1.0))

    def _generate_cache_key(self, notes: List[NoteEvent]) -> str:
        """Generate a cache key for a sequence of notes"""
        return ':'.join(
            f"{note.pitch},{note.velocity},{note.start:.3f},{note.end:.3f},{note.string}"
            for note in notes
        )

    def _update_cache(self, key: str, value: dict):
        """Update the mutation cache with LRU behavior"""
        if len(self.mutation_cache) >= self.cache_size:
            # Remove oldest entry
            oldest_key = next(iter(self.mutation_cache))
            del self.mutation_cache[oldest_key]
        self.mutation_cache[key] = value

    async def generate_problem_section(
        self,
        current_notes: List[NoteEvent],
        performance_metrics: Dict[str, float],
        duration: float = 5.0,
        mutation_strength: Optional[float] = None
    ) -> RiffMutation:
        """
        Generate a problem section based on current performance
        Returns a RiffMutation object containing the problem section notes
        """
        
        if mutation_strength is None:
            mutation_strength = 0.7
        
        request = MutationRequest(
            notes=current_notes,
            mutation_strength=mutation_strength,  # Higher mutation strength for problem sections
            preserve_rhythm=True,
            performance_state=performance_metrics
        )
        
        mutation_response = await self.generate_mutation(request)
        
        return RiffMutation(
            original_notes=mutation_response.original_notes,
            mutated_notes=mutation_response.mutated_notes,
            mutation_type=mutation_response.mutation_type,
            problem_duration=duration,
            timestamp=datetime.now().timestamp()
        )

    def cleanup(self):
        """Cleanup resources"""
        if self.executor:
            self.executor.shutdown(wait=True)
        if self.riff_generator:
            self.riff_generator.cleanup()
            
    async def get_suggested_mutation_strength(
        self,
        performance_metrics: Dict[str, float],
        current_difficulty: str
    ) -> float:
        """
        Calculate suggested mutation strength based on performance and difficulty
        """
        base_strength = {
            'easy': 0.3,
            'medium': 0.5,
            'hard': 0.7,
            'expert': 0.9
        }.get(current_difficulty, 0.5)
        
        # Adjust based on performance
        avg_performance = sum(performance_metrics.values()) / len(performance_metrics)
        
        # Scale adjustment between -0.2 and +0.2 based on performance
        performance_adjustment = ((avg_performance - 70) / 30) * 0.2
        
        return max(0.1, min(1.0, base_strength + performance_adjustment))
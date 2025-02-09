from typing import List, Optional
from datetime import datetime
import numpy as np
import logging

from app.models.schema import (
    NoteEvent,
    ScoreComponent,
    ScoreUpdate,
    ScoreMetrics
)

logger = logging.getLogger(__name__)

class ScoringConfig:
    def __init__(self):
        self.perfect_timing_window = 0.1
        self.good_timing_window = 0.2
        self.acceptable_timing_window = 0.3

        self.perfect_points = 100
        self.good_points = 30
        self.acceptable_points = 20

        self.reaction_weight = 0.4
        self.rhythm_weight = 0.3
        self.creativity_weight = 0.3

        self.combo_threshold = 3
        self.max_combo_multiplier = 4.0
        self.combo_increment = 0.5

        self.difficulty_multipliers = {
            "easy": 0.8,
            "medium": 1.0,
            "hard": 1.2,
            "expert": 1.5
        }

class ScoringService:
    def __init__(self, config: Optional[ScoringConfig] = None):
        self.config = config or ScoringConfig()
        self.state = {}
        self.start_session()  # initialize default state

    def start_session(self) -> None:
        """Initialize a new global scoring session."""
        self.state = {
            "current_score": 0,
            "combo_multiplier": 1.0,
            "combo_count": 0,
            "difficulty": "medium",
            "last_mutation_time": None,
            "recent_scores": [],
            "last_notes": None,
            "metrics": ScoreMetrics(
                creativity_score=0.0,
                reaction_score=0.0,
                rhythm_score=0.0,
                combo_multiplier=1.0,
                total_score=0.0
            )
        }

    def evaluate_adaptation(
        self,
        original_notes: List[NoteEvent],
        player_notes: List[NoteEvent],
        mutation_time: float
    ) -> ScoreUpdate:
        current_time = datetime.now().timestamp()

        reaction_score = self._calculate_reaction_score(
            mutation_time, player_notes, current_time
        )

        rhythm_score = self._calculate_rhythm_score(original_notes, player_notes)

        creativity_score = self._calculate_creativity_score(
            original_notes, player_notes, self.state["last_notes"]
        )

        self.state["metrics"].reaction_score = reaction_score
        self.state["metrics"].rhythm_score = rhythm_score
        self.state["metrics"].creativity_score = creativity_score

        base_score = (
            (reaction_score * self.config.reaction_weight) +
            (rhythm_score * self.config.rhythm_weight) +
            (creativity_score * self.config.creativity_weight)
        )

        difficulty_multiplier = self.config.difficulty_multipliers[self.state["difficulty"]]

        if base_score >= self.config.good_points:
            self.state["combo_count"] += 1
            self.state["combo_multiplier"] = min(
                1.0 + (self.state["combo_count"] * self.config.combo_increment),
                self.config.max_combo_multiplier
            )
        else:
            self.state["combo_count"] = 0
            self.state["combo_multiplier"] = 1.0

        final_score = base_score * difficulty_multiplier * self.state["combo_multiplier"]

        self.state["current_score"] += final_score
        self.state["last_mutation_time"] = mutation_time
        self.state["last_notes"] = player_notes
        self.state["recent_scores"].append(base_score)
        if len(self.state["recent_scores"]) > 5:
            self.state["recent_scores"].pop(0)

        self._adjust_difficulty()

        components = [
            ScoreComponent(
                category="reaction",
                value=reaction_score,
                weight=self.config.reaction_weight,
                timestamp=current_time
            ),
            ScoreComponent(
                category="rhythm",
                value=rhythm_score,
                weight=self.config.rhythm_weight,
                timestamp=current_time
            ),
            ScoreComponent(
                category="creativity",
                value=creativity_score,
                weight=self.config.creativity_weight,
                timestamp=current_time
            )
        ]

        return ScoreUpdate(
            components=components,
            total_score=self.state["current_score"],
            session_id="global",  # Optional; you can remove this field if desired.
            timestamp=current_time
        )

    def _calculate_reaction_score(self, mutation_time, player_notes, current_time):
        if not player_notes:
            return 0
        first_note_time = min(note.start for note in player_notes)
        reaction_time = first_note_time - mutation_time
        if reaction_time <= self.config.perfect_timing_window:
            return self.config.perfect_points
        elif reaction_time <= self.config.good_timing_window:
            return self.config.good_points
        elif reaction_time <= self.config.acceptable_timing_window:
            return self.config.acceptable_points
        else:
            return max(0, self.config.acceptable_points * 
                       (1 - (reaction_time - self.config.acceptable_timing_window)))

    def _calculate_rhythm_score(self, original_notes, player_notes):
        if not original_notes or not player_notes:
            return 0
        original_timings = np.array([note.start for note in original_notes])
        player_timings = np.array([note.start for note in player_notes])
        timing_errors = []
        for orig_time in original_timings:
            if len(player_timings) > 0:
                closest_idx = np.argmin(np.abs(player_timings - orig_time))
                error = abs(player_timings[closest_idx] - orig_time)
                timing_errors.append(error)
        if not timing_errors:
            return 0
        avg_error = np.mean(timing_errors)
        if avg_error <= self.config.perfect_timing_window:
            return self.config.perfect_points
        elif avg_error <= self.config.good_timing_window:
            return self.config.good_points
        elif avg_error <= self.config.acceptable_timing_window:
            return self.config.acceptable_points
        else:
            return max(0, self.config.acceptable_points * 
                       (1 - (avg_error - self.config.acceptable_timing_window)))

    def _calculate_creativity_score(self, original_notes, player_notes, last_notes):
        if not original_notes or not player_notes:
            return 0
        score = 0
        pitch_score = self._evaluate_pitch_coherence(original_notes, player_notes)
        score += pitch_score * 0.4
        rhythm_score = self._evaluate_rhythmic_variation(original_notes, player_notes, last_notes)
        score += rhythm_score * 0.3
        development_score = self._evaluate_musical_development(original_notes, player_notes, last_notes)
        score += development_score * 0.3
        return score

    def _evaluate_pitch_coherence(
        self,
        original_notes: List[NoteEvent],
        player_notes: List[NoteEvent]
    ) -> float:
        original_pitches = [note.pitch for note in original_notes]
        player_pitches = [note.pitch for note in player_notes]
        original_intervals = np.diff(original_pitches)
        player_intervals = np.diff(player_pitches)
        if len(original_intervals) == 0 or len(player_intervals) == 0:
            return 0
        matched_intervals = 0
        for orig_int, player_int in zip(original_intervals, player_intervals):
            if (np.sign(orig_int) == np.sign(player_int) or
                abs(orig_int - player_int) in [0, 7, 12]):  # Unison, fifth, octave
                matched_intervals += 1
        coherence_score = (matched_intervals / len(original_intervals)) * 100
        return coherence_score

    def _evaluate_rhythmic_variation(
        self,
        original_notes: List[NoteEvent],
        player_notes: List[NoteEvent],
        last_notes: Optional[List[NoteEvent]]
    ) -> float:
        if not last_notes:
            return self.config.good_points  # Base score for first attempt
        original_density = len(original_notes)
        player_density = len(player_notes)
        last_density = len(last_notes)
        density_change = abs(player_density - last_density)
        if density_change > 0 and player_density >= original_density * 0.8:
            return self.config.perfect_points
        elif player_density >= original_density * 0.9:
            return self.config.good_points
        else:
            return self.config.acceptable_points

    def _evaluate_musical_development(
        self,
        original_notes: List[NoteEvent],
        player_notes: List[NoteEvent],
        last_notes: Optional[List[NoteEvent]]
    ) -> float:
        if not last_notes:
            return self.config.good_points  # Base score for first attempt
        score = 0
        motif_score = self._analyze_motif_development(
            original_notes,
            player_notes,
            last_notes
        )
        score += motif_score * 0.5  # 50% weight
        phrase_score = self._analyze_phrase_structure(
            player_notes,
            last_notes
        )
        score += phrase_score * 0.5  # 50% weight
        return score

    def _analyze_motif_development(
        self,
        original_notes: List[NoteEvent],
        player_notes: List[NoteEvent],
        last_notes: List[NoteEvent]
    ) -> float:
        pattern_length = 3
        def get_patterns(notes):
            return [
                tuple(note.pitch for note in notes[i:i+pattern_length])
                for i in range(len(notes) - pattern_length + 1)
            ]
        original_patterns = get_patterns(original_notes)
        player_patterns = get_patterns(player_notes)
        related_patterns = 0
        for player_pattern in player_patterns:
            for orig_pattern in original_patterns:
                if self._are_patterns_related(player_pattern, orig_pattern):
                    related_patterns += 1
                    break
        if len(player_patterns) == 0:
            return 0
        return (related_patterns / len(player_patterns)) * 100

    def _analyze_phrase_structure(
        self,
        player_notes: List[NoteEvent],
        last_notes: List[NoteEvent]
    ) -> float:
        def get_phrase_boundaries(notes):
            boundaries = []
            for i in range(1, len(notes)):
                gap = notes[i].start - notes[i-1].end
                if gap > 0.5:  # More than 500ms gap
                    boundaries.append(i)
            return boundaries
        player_boundaries = get_phrase_boundaries(player_notes)
        if len(player_boundaries) > 0:
            return self.config.perfect_points
        else:
            return self.config.acceptable_points

    def _are_patterns_related(
        self,
        pattern1: tuple,
        pattern2: tuple
    ) -> bool:
        if len(pattern1) != len(pattern2):
            return False
        intervals1 = np.diff(pattern1)
        intervals2 = np.diff(pattern2)
        return np.array_equal(intervals1, intervals2)

    def _adjust_difficulty(self):
        if len(self.state["recent_scores"]) < 5:
            return
        avg_score = np.mean(self.state["recent_scores"])
        current_difficulty = self.state["difficulty"]
        if current_difficulty == "easy" and avg_score > 85:
            self.state["difficulty"] = "medium"
            logger.info(f"Difficulty increased to medium (avg_score: {avg_score})")
        elif current_difficulty == "medium" and avg_score > 90:
            self.state["difficulty"] = "hard"
            logger.info(f"Difficulty increased to hard (avg_score: {avg_score})")
        elif current_difficulty == "hard" and avg_score > 95:
            self.state["difficulty"] = "expert"
            logger.info(f"Difficulty increased to expert (avg_score: {avg_score})")
        elif avg_score < 60:
            if current_difficulty == "expert":
                self.state["difficulty"] = "hard"
            elif current_difficulty == "hard":
                self.state["difficulty"] = "medium"
            elif current_difficulty == "medium":
                self.state["difficulty"] = "easy"
            logger.info(f"Difficulty decreased to {self.state['difficulty']} (avg_score: {avg_score})")

    def end_session(self) -> ScoreMetrics:
        """
        End the session, return final metrics, and reset the state for a new session.
        """
        metrics = self.state["metrics"]
        metrics.total_score = self.state["current_score"]
        metrics.combo_multiplier = self.state["combo_multiplier"]
        self.start_session()
        return metrics

    def reset_combo(self) -> None:
        """Reset the combo counters for the current session."""
        self.state["combo_count"] = 0
        self.state["combo_multiplier"] = 1.0

    def update_difficulty(self, difficulty: str) -> None:
        """Manually update the difficulty for the current session."""
        if difficulty not in self.config.difficulty_multipliers:
            raise ValueError(f"Invalid difficulty level: {difficulty}")
        self.state["difficulty"] = difficulty
        logger.info(f"Difficulty manually set to {difficulty}")

    def cleanup(self) -> None:
        """Cleanup the current session state."""
        self.state.clear()

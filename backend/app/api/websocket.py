from fastapi import WebSocket, APIRouter
from typing import List, Optional, Dict, Any, Union
import asyncio
import logging
from datetime import datetime
from fastapi.encoders import jsonable_encoder
import numpy as np

from app.models.schema import (
    WebSocketMessage,
    GameState,
    NoteEvent,
    NoteHitEvent,
    ScoreUpdate,
    MessageType
)
from app.services.adaptive_mutation import AdaptiveMutationService
from app.services.audio_processor import AudioProcessorService
from app.services.inference import InferenceService
from app.services.scoring import ScoringService

router = APIRouter()
logger = logging.getLogger(__name__)

class GameSession:
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.state = GameState()
        self.note_counter = 0
        self.scoring_service = ScoringService()
        self.inference_service = InferenceService()
        self.adaptive_mutation = AdaptiveMutationService()  # Adaptive mutation service initialized
        self.problem_cooldown = False
        self.freestyle_notes = []  # To record freestyle notes during the problem section
        self.session_start_time = datetime.now().timestamp()
        self.last_problem_trigger_time = 0  # Timestamp of the last triggered problem section
        logger.info("New game session initialized")

    def should_trigger_problem(self) -> bool:
        """
        Determine whether a problem section should be triggered.
        Conditions:
            - At least 15 seconds have elapsed since the session started.
            - At least 15 seconds have elapsed since the last problem section.
            - Additional condition (for example, a minimum combo threshold).
        """
        current_time = datetime.now().timestamp()
        if current_time - self.session_start_time < 15:
            return False
        if current_time - self.last_problem_trigger_time < 15:
            return False
        if self.state.combo < 5:
            return False
        return True

    async def trigger_problem_section(self):
        logger.info("Starting problem section sequence")
        self.problem_cooldown = True

        # First, generate the problem section
        performance_metrics = {
            "creativity": self.scoring_service.state["metrics"].creativity_score,
            "reaction": self.scoring_service.state["metrics"].reaction_score,
            "rhythm": self.scoring_service.state["metrics"].rhythm_score
        }

        problem_section_duration = 7.0

        # Generate the problem section mutation
        problem_section = await self.inference_service.generate_problem_section(
            self.state.current_notes,
            performance_metrics,
            duration=problem_section_duration
        )
        self.state.problem_section = problem_section

        # Send warning first
        await self.send_message(MessageType.PROBLEM_WARNING, {
            "warning": "Problem section incoming",
            "duration": 5  # Warning duration in seconds
        })

        # Wait 5 seconds
        await asyncio.sleep(5)

        # Now send the actual problem start with the generated notes
        self.state.mode = "problem"
        self.freestyle_notes = []
        await self.send_message(MessageType.PROBLEM_START, problem_section.dict())

        # Wait for the problem section duration
        await asyncio.sleep(problem_section.problem_duration)

        # End the problem section and process freestyle notes
        await self.end_problem_section()

    async def end_problem_section(self):
        logger.info("Ending problem section")
        # Analyze freestyle notes to see if the user performed well compared to the problem section's original notes.
        good_freestyle_notes = self.analyze_freestyle_notes()

        if good_freestyle_notes:
            logger.info(f"Incorporating {len(good_freestyle_notes)} good freestyle notes into future sequence")
            # For simplicity, append the good freestyle notes to the current sequence.
            self.state.current_notes.extend([note.dict() for note in good_freestyle_notes])
        else:
            logger.info("No good freestyle notes to incorporate.")

        # Reset the problem section state and return to normal gameplay.
        self.state.problem_section = None
        self.freestyle_notes = []
        self.state.mode = "game"
        await self.send_message(MessageType.PROBLEM_END, {"mode": "game", "current_notes": self.state.current_notes})
        self.problem_cooldown = False

    def analyze_freestyle_notes(self) -> List[NoteEvent]:
        """
        Analyze freestyle notes by comparing them with the original notes of the problem section.
        For example, if a freestyle note's pitch deviates by at most 1 semitone from an original note,
        consider it a “good” note.
        """
        good_notes = []
        if self.state.problem_section and self.state.problem_section.original_notes:
            original_notes = self.state.problem_section.original_notes
            for freestyle_note in self.freestyle_notes:
                for original_note in original_notes:
                    if abs(freestyle_note.pitch - original_note.pitch) <= 1:
                        good_notes.append(freestyle_note)
                        break
        return good_notes

    async def handle_note_hit(self, hit_event: NoteHitEvent):
        try:
            logger.debug(f"Processing note hit: {hit_event}")

            matching_note = next(
                (n for n in self.current_notes if 
                    (isinstance(n, dict) and n.get('id') == hit_event.note_id) or
                    (isinstance(n, NoteEvent) and n.id == hit_event.note_id)
                ),
                None
            )

            if not matching_note:
                logger.debug(f"No matching note found for id: {hit_event.note_id}")
                return

            if isinstance(matching_note, dict):
                note_event = NoteEvent(**matching_note)
            else:
                note_event = matching_note

            # If in problem mode, record the freestyle note and bypass regular scoring.
            if self.state.mode == "problem":
                logger.debug(f"Recording freestyle note during problem section: {note_event}")
                self.freestyle_notes.append(note_event)
                await self.send_message(MessageType.NOTE_HIT, note_event.dict())
                return

            if self.state.is_paused:
                # Skip any new note generation or scoring logic
                return

            # Log state before evaluation
            logger.debug(f"Pre-evaluation state - Score: {self.state.score}, Combo: {self.state.combo}")

            current_time = datetime.now().timestamp()

            # Evaluate the hit using regular scoring
            score_update = self.scoring_service.evaluate_adaptation(
                [NoteEvent(**n) if isinstance(n, dict) else n for n in self.current_notes],
                [note_event],
                current_time
            )

            # Update local state based on evaluation
            self.state.score = score_update.total_score
            self.state.combo = int(self.scoring_service.state["combo_count"])

            logger.debug(f"Post-evaluation state - Score: {self.state.score}, Combo: {self.state.combo}")

            # Send score update first, then session state update
            await self.send_message(
                MessageType.SCORE_UPDATE,
                {
                    "score": self.state.score,
                    "total_score": score_update.total_score,
                    "combo": self.scoring_service.state["combo_count"],
                    "combo_multiplier": self.scoring_service.state["combo_multiplier"]
                }
            )

            await self.send_message(
                MessageType.SESSION_STATE,
                self.state.serialize
            )

            # Check if conditions trigger the problem section
            if not self.problem_cooldown and self.should_trigger_problem():
                # Update the last trigger time and trigger the problem section.
                self.last_problem_trigger_time = datetime.now().timestamp()
                await self.trigger_problem_section()

        except Exception as e:
            logger.error(f"Error handling note hit: {str(e)}", exc_info=True)
            await self.send_message(
                MessageType.ERROR,
                {"error": f"Failed to process note hit: {str(e)}"}
            )

    @property
    def current_notes(self):
        """Property to access current notes from state"""
        return self.state.current_notes

    async def send_message(self, message_type: MessageType, payload: Dict[str, Any]):
        try:
            message = WebSocketMessage(
                type=message_type,
                payload=payload,
                timestamp=datetime.now().timestamp()
            )
            encoded_message = jsonable_encoder(message.dict())
            await self.websocket.send_json(encoded_message)
            logger.debug(f"Sent WebSocket message: {message_type} with payload: {payload}")
        except Exception as e:
            logger.error(f"Error sending WebSocket message: {str(e)}", exc_info=True)

    async def end_game_session(self):
        logger.info("Ending game session. Calculating final metrics...")
        final_metrics = {
            "final_score": self.state.score,
            "final_combo": self.state.combo,
            "total_notes": len(self.state.current_notes),
            "time_played": datetime.now().timestamp() - self.session_start_time
        }
        # Mark session as inactive.
        self.state.is_active = False
        await self.send_message(MessageType.SESSION_END, final_metrics)

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    session = None
    try:
        await websocket.accept()
        logger.info("WebSocket connection accepted")

        session = GameSession(websocket)

        # Send initial state
        await session.send_message(
            MessageType.SESSION_STATE, 
            {
                "is_active": True,
                "mode": "waiting",
                "score": 0,
                "combo": 0,
                "combo_multiplier": 1.0
            }
        )

        while True:
            message = await websocket.receive_json()
            logger.debug(f"Received message: {message}")

            message_type = message.get("type")
            if not message_type:
                continue

            payload = message.get("payload", {})

            if message_type == MessageType.SESSION_STATE:
                if "notes" in payload or "current_notes" in payload:
                    note_key = "notes" if "notes" in payload else "current_notes"
                    notes = []
                    for i, note in enumerate(payload[note_key]):
                        if isinstance(note, dict):
                            if 'id' not in note:
                                note['id'] = i
                            notes.append(note)
                        else:
                            notes.append(note)
                    # Sort notes by their timestamp (start property)
                    notes = sorted(notes, key=lambda n: n['start'])
                    session.state.current_notes = notes

                # Update other state properties as needed
                for key, value in payload.items():
                    if hasattr(session.state, key) and key != "current_notes":
                        setattr(session.state, key, value)

                # Send updated state with sorted notes
                await session.send_message(
                    MessageType.SESSION_STATE,
                    {
                        "is_active": session.state.is_active,
                        "mode": session.state.mode,
                        "score": session.state.score,
                        "combo": session.state.combo,
                        "combo_multiplier": session.scoring_service.state["combo_multiplier"],
                        "current_notes": session.state.current_notes
                    }
                )

            elif message_type == MessageType.NOTE_HIT:
                hit_event = NoteHitEvent(**payload)
                session.state.last_hit_time = hit_event.hit_time
                await session.handle_note_hit(hit_event)

            elif message_type == MessageType.NOTE_MISS:
                logger.debug(f"NOTE_MISS received: {payload}")

                session.scoring_service.state["combo_count"] = 0
                session.scoring_service.state["combo_multiplier"] = 1.0
                session.state.combo = 0  # keep session.state in sync

                await session.send_message(
                    MessageType.SESSION_STATE,
                    session.state.serialize
                )

            elif message_type == MessageType.PAUSE_GAME:
                logger.info("Received PAUSE_GAME from client")
                session.state.is_paused = True
                await session.send_message(MessageType.SESSION_STATE, session.state.serialize)

            elif message_type == MessageType.RESUME_GAME:
                logger.info("Received RESUME_GAME from client")
                session.state.is_paused = False
                await session.send_message(MessageType.SESSION_STATE, session.state.serialize)

            elif message_type == MessageType.END_GAME:
                logger.info("Received END_GAME message. Ending session.")
                await session.end_game_session()
                break

    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}", exc_info=True)
    finally:
        if session:
            logger.info("Cleaning up session")
            try:
                session.state.is_active = False
                await session.send_message(
                    MessageType.SESSION_STATE,
                    {
                        "is_active": False,
                        "mode": session.state.mode,
                        "score": session.state.score,
                        "combo": session.state.combo
                    }
                )
            except Exception as cleanup_error:
                logger.error(f"Error during cleanup: {str(cleanup_error)}")

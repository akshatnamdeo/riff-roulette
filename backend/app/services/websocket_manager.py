from fastapi import WebSocket
from typing import Optional
import asyncio
import logging
from datetime import datetime
from fastapi.encoders import jsonable_encoder

from app.models.schema import WebSocketMessage, MessageType, SessionState, ErrorMessage

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.connection: Optional[WebSocket] = None
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self.background_task: Optional[asyncio.Task] = None
        self.session_state: Optional[SessionState] = None

    async def connect(self, websocket: WebSocket) -> None:
        try:
            await websocket.accept()
            self.connection = websocket
            self.session_state = SessionState(
                session_id="global",
                start_time=datetime.now(),
                is_active=True
            )
            self.background_task = asyncio.create_task(self._process_message_queue())
            await self.send_message(MessageType.SESSION_STATE, self.session_state.dict())
            logger.info("Client connected (global session).")
        except Exception as e:
            logger.error(f"Error in connect: {str(e)}")
            await self.disconnect()
            raise

    async def disconnect(self) -> None:
        try:
            if self.connection:
                await self.connection.close()
                self.connection = None
            if self.session_state:
                self.session_state.is_active = False
            logger.info("Client disconnected (global session).")
        except Exception as e:
            logger.error(f"Error in disconnect: {str(e)}")

    async def send_message(self, message_type: MessageType, payload: dict) -> None:
        if not self.connection:
            logger.warning("Attempted to send message without an active connection.")
            return
        try:
            message = WebSocketMessage(
                type=message_type,
                payload=payload,
                session_id="global"
            )
            # Convert the message to a JSON‑serializable format:
            encoded_message = jsonable_encoder(message.dict())
            await self.connection.send_json(encoded_message)
        except Exception as e:
            logger.error(f"Error sending message: {str(e)}")
            await self.handle_error("MESSAGE_SEND_ERROR", str(e))

    async def handle_error(self, error_code: str, message: str, details: Optional[dict] = None) -> None:
        error = ErrorMessage(
            code=error_code,
            message=message,
            details=details,
            timestamp=datetime.now().timestamp()
        )
        try:
            await self.send_message(MessageType.ERROR, error.dict())
        except Exception as e:
            logger.error(f"Error sending error message: {str(e)}")

    async def _process_message_queue(self) -> None:
        try:
            while self.connection:
                message_type, payload = await self.message_queue.get()
                try:
                    await self.send_message(message_type, payload)
                except Exception as e:
                    logger.error(f"Error processing queued message: {str(e)}")
                finally:
                    self.message_queue.task_done()
        except asyncio.CancelledError:
            logger.info("Message queue processor cancelled (global session).")
        except Exception as e:
            logger.error(f"Error in message queue processor: {str(e)}")

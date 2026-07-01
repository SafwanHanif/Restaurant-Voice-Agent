"""
Updated browser bridge with proper WebSocket handling for browser connections.
This fixes the browser widget integration issues.
"""

import asyncio
import json
import uuid
from datetime import date

from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.tools.definitions import TOOL_DECLARATIONS, handle_tool_call
from app.voice.bridge import load_system_prompt
from app.voice.gemini_live import GeminiLiveSession

class BrowserWebSocketConnection:
    """Enhanced WebSocket connection handler for browser clients."""

    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.connection_id = str(uuid.uuid4())[:8]
        self.gemini_session: GeminiLiveSession | None = None
        self.audio_buffer = b""
        self.text_buffer = b""

    async def accept_connection(self):
        """Accept and initialize the WebSocket connection."""
        await self.websocket.accept()
        logger.info(f"[{self.connection_id}] Browser WebSocket connection accepted")
        return True

    async def setup_gemini_session(self):
        """Create and start Gemini Live session for this connection."""
        try:
            # Load the system prompt with today's date
            system_prompt = await load_system_prompt()

            async def on_tool_call(tool_name: str, args: dict):
                """Handle a tool call by dispatching to restaurant services."""
                async with async_session_factory() as db_session:
                    return await handle_tool_call(db_session, tool_name, args)

            self.gemini_session = GeminiLiveSession(
                system_prompt=system_prompt,
                tool_declarations=TOOL_DECLARATIONS,
                on_tool_call=on_tool_call,
            )
            await self.gemini_session.start()
            logger.info(f"[{self.connection_id}] Gemini Live session active")

            return True
        except Exception as e:
            logger.error(f"[{self.connection_id}] Failed to setup Gemini session: {e}")
            return False

    async def send_connection_ready(self):
        """Send connection ready message to browser (as per protocol)."""
        await self.websocket.send_json({
            "type": "connected",
            "message": "Connected to Bella Italia voice assistant. Start speaking!",
            "connection_id": self.connection_id
        })
        logger.info(f"[{self.connection_id}] Sent connection ready message")

    async def process_audio_data(self, audio_bytes: bytes):
        """Process incoming audio data from browser."""
        if not audio_bytes:
            return

        # Add to buffer and forward to Gemini
        self.audio_buffer += audio_bytes
        await self.gemini_session.push_audio(audio_bytes)
        logger.debug(f"[{self.connection_id}] Forwarded {len(audio_bytes)} bytes to Gemini")

    async def process_text_message(self, text_bytes: bytes):
        """Process text control messages from browser."""
        try:
            text = text_bytes.decode('utf-8')
            logger.debug(f"[{self.connection_id}] Received text message: {text}")

            # Parse JSON if possible
            try:
                msg = json.loads(text)
                msg_type = msg.get('type', '')

                if msg_type == 'stop':
                    logger.info(f"[{self.connection_id}] Stop message received, closing connection")
                    await self.close()
                    return

                # Handle other control messages
                if msg_type == 'ping':
                    await self.websocket.send_json({
                        "type": "pong",
                        "timestamp": time.time()
                    })

            except json.JSONDecodeError:
                # Not JSON, treat as raw text
                logger.debug(f"[{self.connection_id}] Non-JSON text message: {text}")

        except UnicodeDecodeError:
            logger.warning(f"[{self.connection_id}] Could not decode text message")
        except Exception as e:
            logger.error(f"[{self.connection_id}] Error processing text message: {e}")

    async def relay_gemini_responses(self):
        """Forward Gemini's responses to browser (audio + text)."""
        if not self.gemini_session:
            return

        try:
            async for event in self.gemini_session.audio_output_stream():
                if not self.gemini_session:
                    break

                if event["type"] == "audio":
                    # Send raw PCM16 audio to browser
                    await self.websocket.send_bytes(bytes(event["data"]))
                    logger.debug(f"[{self.connection_id}] Sent {len(event['data'])} bytes of audio to browser")

                elif event["type"] == "text":
                    # Send text as JSON to browser
                    await self.websocket.send_json({
                        "type": "text",
                        "text": event["text"],
                        "timestamp": time.time()
                    })
                    logger.debug(f"[{self.connection_id}] Sent transcript to browser: {event['text'][:50]}...")

        except Exception as e:
            if "close" not in str(e).lower():
                logger.error(f"[{self.connection_id}] Error in response relay: {e}")

    async def start_relay_tasks(self):
        """Start the response relay task."""
        if not self.gemini_session:
            return

        relay_task = asyncio.create_task(self.relay_gemini_responses())
        return relay_task

    async def close(self):
        """Cleanly close the connection and session."""
        logger.info(f"[{self.connection_id}] Closing connection")

        # Close Gemini session
        if self.gemini_session:
            try:
                await self.gemini_session.close()
                logger.info(f"[{self.connection_id}] Gemini session closed")
            except Exception as e:
                logger.error(f"[{self.connection_id}] Error closing Gemini session: {e}")

        # Close WebSocket
        try:
            await self.websocket.close()
            logger.info(f"[{self.connection_id}] WebSocket closed")
        except Exception as e:
            logger.error(f"[{self.connection_id}] Error closing WebSocket: {e}")

import time
from fastapi import FastAPI
from fastapi.websocketsimplestatemachine import WebSocketState
from app.voice.bridge import load_system_prompt as bridge_load_system_prompt

# Mock time for testing
class MockTime:
    @staticmethod
    def time():
        return time.time()

# Replace time.time for consistent testing
time.time = MockTime.time

async def handle_browser_session(websocket: WebSocket):
    """
    Enhanced browser WebSocket connection handler with proper protocol support.

    Protocol:
    1. Client connects to /voice/browser
    2. Server sends {"type": "connected", "message": "..."}
    3. Client streams PCM16 audio as binary messages
    4. Server sends back PCM16 audio + JSON text messages
    6. Either client or server closes the connection

    The browser expects:
    - Initial connection acknowledgment
    - Audio streaming in both directions
    - Text transcripts for UI updates
    """
    connection = BrowserWebSocketConnection(websocket)

    try:
        # Step 1: Accept connection
        await connection.accept_connection()

        # Step 2: Setup Gemini session
        if not await connection.setup_gemini_session():
            logger.error("Failed to setup Gemini session, closing connection")
            return

        # Step 3: Send connection ready message (browser expects this)
        await connection.send_connection_ready()

        # Step 4: Start response relay task
        relay_task = await connection.start_relay_tasks()

        # Step 5: Main processing loop - handle incoming messages
        while True:
            try:
                # Use receive() with timeout to allow graceful shutdown
                raw = await asyncio.wait_for(
                    websocket.receive(),
                    timeout=1.0
                )

                # Handle WebSocket disconnect
                if raw.get("type") == "websocket.disconnect":
                    logger.info(f"[{connection.connection_id}] WebSocket disconnect event received")
                    break

                # Process audio data (binary messages)
                if "bytes" in raw:
                    audio_bytes = raw["bytes"]
                    if audio_bytes:  # Check for empty bytes
                        await connection.process_audio_data(audio_bytes)

                # Process text messages
                elif "text" in raw:
                    text_bytes = raw["text"].encode('utf-8')
                    await connection.process_text_message(text_bytes)

            except asyncio.TimeoutError:
                # Timeout is normal - just continue waiting for messages
                continue
            except WebSocketDisconnect:
                logger.info(f"[{connection.connection_id}] WebSocket disconnected")
                break
            except Exception as e:
                logger.error(f"[{connection.connection_id}] Error in main loop: {e}")
                break

    except WebSocketDisconnect:
        logger.info(f"[{connection.connection_id}] Browser WebSocket disconnected")
    except Exception as e:
        logger.error(f"[{connection.connection_id}] Browser bridge error: {e}", exc_info=True)
    finally:
        # Cleanup
        logger.info(f"[{connection.connection_id}] Cleaning up connection")
        relay_task = getattr(connection, 'relay_task', None)
        if relay_task and not relay_task.done():
            relay_task.cancel()
            try:
                await relay_task
            except asyncio.CancelledError:
                pass

        await connection.close()
        logger.info(f"[{connection.connection_id}] Browser session ended")

# Export the function for main.py
__all__ = ["handle_browser_session"]
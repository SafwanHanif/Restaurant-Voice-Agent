"""
Fixed browser bridge with proper WebSocket protocol.

Protocol Fix:
1. Server sends "connected" message immediately after accepting connection
2. Browser sends "client_ready" message after connection
3. Both sides then exchange audio and JSON messages bidirectionally
"""

import asyncio
import json
import time
from datetime import date
from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.tools.definitions import TOOL_DECLARATIONS, handle_tool_call
from app.voice.bridge import load_system_prompt
from app.voice.gemini_live import GeminiLiveSession

class FixedBrowserWebSocketConnection:
    """
    Fixed WebSocket connection handler with proper protocol support.

    Protocol:
    1. Client connects to /voice/browser
    2. Server sends {"type": "connected", ...} immediately (server-initiated)
    3. Client sends {"type": "client_ready", ...} (client handshake)
    4. Server processes audio and JSON messages from client
    5. Server sends binary audio and JSON responses back to client
    6. Either side closes the connection
    """

    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.connection_id = f"ws_{int(time.time() * 1000) % 10000}"
        self.gemini_session: GeminiLiveSession | None = None
        self.client_ready_received = False
        self.handshake_time = None
        self.last_activity = time.time()

    async def accept_connection(self):
        """Accept and initialize the WebSocket connection."""
        await self.websocket.accept()
        logger.info(f"[{self.connection_id}] Browser WebSocket connection accepted")
        self.handshake_time = time.time()
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

    async def send_immediate_connection_ready(self):
        """Send immediate connection ready message (server-initiated)."""
        await self.websocket.send_json({
            "type": "connected",
            "message": "Connected to Bella Italia voice assistant. Start speaking!",
            "connection_id": self.connection_id,
            "timestamp": self.handshake_time,
            "protocol_version": "1.0"
        })
        logger.info(f"[{self.connection_id}] Sent immediate connection ready message")

    async def send_client_ready_response(self, client_data: dict):
        """Send response after receiving client_ready message."""
        await self.websocket.send_json({
            "type": "client_handshake_ack",
            "message": "Client ready confirmed. Voice assistant is listening.",
            "connection_id": self.connection_id,
            "timestamp": time.time(),
            "client_id": client_data.get("client_id"),
            "status": "ready"
        })
        logger.info(f"[{self.connection_id}] Sent client handshake acknowledgment")

    async def process_audio_data(self, audio_bytes: bytes):
        """Process incoming audio data from browser."""
        if not audio_bytes:
            return

        current_time = time.time()
        self.last_activity = current_time

        # Validate audio chunk size (should be reasonable for voice)
        if len(audio_bytes) > 1024 * 1024:  # 1MB max (2 seconds at 16kHz 16-bit)
            logger.warning(f"[{self.connection_id}] Audio chunk unusually large: {len(audio_bytes)} bytes")

        # Forward audio to Gemini
        if self.gemini_session:
            try:
                await self.gemini_session.push_audio(audio_bytes)
                logger.debug(f"[{self.connection_id}] Forwarded {len(audio_bytes)} bytes to Gemini")
            except Exception as e:
                logger.error(f"[{self.connection_id}] Error forwarding audio: {e}")
        else:
            logger.warning(f"[{self.connection_id}] Received audio but no Gemini session")

    async def process_text_message(self, text_bytes: bytes):
        """Process text control messages from browser."""
        try:
            text = text_bytes.decode('utf-8')
            self.last_activity = time.time()
            logger.debug(f"[{self.connection_id}] Received text message: {text}")

            # Parse JSON if possible
            try:
                msg = json.loads(text)
                msg_type = msg.get('type', '')

                if msg_type == 'client_ready':
                    # This is the expected client handshake
                    if not self.client_ready_received:
                        self.client_ready_received = True
                        await self.send_client_ready_response(msg)
                        logger.info(f"[{self.connection_id}] Client handshake completed")
                    else:
                        logger.debug(f"[{self.connection_id}] Duplicate client_ready ignored")

                elif msg_type == 'ping':
                    # Respond to ping with pong
                    await self.websocket.send_json({
                        "type": "pong",
                        "timestamp": time.time()
                    })
                    logger.debug(f"[{self.connection_id}] Pong response sent")

                elif msg_type == 'stop':
                    # Explicit stop request
                    logger.info(f"[{self.connection_id}] Stop requested by client")
                    await self.close()
                    return

                else:
                    logger.debug(f"[{self.connection_id}] Unknown message type: {msg_type}")

            except json.JSONDecodeError:
                # Not JSON, could be raw transcript or other text
                logger.debug(f"[{self.connection_id}] Non-JSON text message: {text[:100]}...")

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

                self.last_activity = time.time()

                if event["type"] == "audio":
                    # Send raw PCM16 audio to browser
                    audio_data = event["data"]
                    if isinstance(audio_data, bytes):
                        await self.websocket.send_bytes(audio_data)
                        logger.debug(f"[{self.connection_id}] Sent {len(audio_data)} bytes of audio to browser")
                    else:
                        logger.warning(f"[{self.connection_id}] Audio data not bytes type: {type(audio_data)}")

                elif event["type"] == "text":
                    # Send transcript as JSON to browser
                    text_data = event["text"]
                    await self.websocket.send_json({
                        "type": "transcript",
                        "text": text_data,
                        "timestamp": time.time(),
                        "connection_id": self.connection_id
                    })
                    logger.debug(f"[{self.connection_id}] Sent transcript: {text_data[:50]}...")

                elif event["type"] == "tool_call":
                    # Tool call results (JSON)
                    await self.websocket.send_json({
                        "type": "tool_result",
                        "result": event,
                        "timestamp": time.time(),
                        "connection_id": self.connection_id
                    })
                    logger.info(f"[{self.connection_id}] Sent tool result: {event.get('name', 'unknown')}")

        except Exception as e:
            if "close" not in str(e).lower():
                logger.error(f"[{self.connection_id}] Error in Gemini response relay: {e}")

    async def start_relay_tasks(self):
        """Start the response relay task."""
        if not self.gemini_session:
            return None

        relay_task = asyncio.create_task(self.relay_gemini_responses())
        return relay_task

    async def monitor_connection_health(self):
        """Monitor connection health and timeout idle connections."""
        while self.gemini_session and self.websocket:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds

                if time.time() - self.last_activity > 300:  # 5 minutes timeout
                    logger.info(f"[{self.connection_id}] Connection idle for 5+ minutes, closing")
                    await self.close()
                    break

                # Send periodic heartbeat
                if time.time() - self.last_activity > 60:  # 1 minute
                    await self.websocket.send_json({
                        "type": "heartbeat",
                        "timestamp": time.time(),
                        "connection_id": self.connection_id
                    })
                    logger.debug(f"[{self.connection_id}] Heartbeat sent")

            except Exception as e:
                logger.warning(f"[{self.connection_id}] Error in health monitor: {e}")
                break

    async def close(self):
        """Cleanly close the connection and session."""
        logger.info(f"[{self.connection_id}] Closing connection")

        # Close health monitor
        # (would need to store the task reference in production)

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

    async def start_health_monitor(self):
        """Start the connection health monitoring."""
        health_monitor = asyncio.create_task(self.monitor_connection_health())
        return health_monitor

    async def wait_for_messages(self, relay_task, health_task):
        """Wait for incoming messages from browser."""
        try:
            while True:
                try:
                    # Use receive() with timeout to allow graceful shutdown
                    raw = await asyncio.wait_for(
                        self.websocket.receive(),
                        timeout=1.0
                    )

                    # Handle WebSocket disconnect
                    if raw.get("type") == "websocket.disconnect":
                        logger.info(f"[{self.connection_id}] WebSocket disconnect event received")
                        break

                    # Process audio data (binary messages)
                    if "bytes" in raw:
                        audio_bytes = raw["bytes"]
                        if audio_bytes:  # Check for empty bytes
                            await self.process_audio_data(audio_bytes)

                    # Process text messages
                    elif "text" in raw:
                        text_bytes = raw["text"].encode('utf-8')
                        await self.process_text_message(text_bytes)

                except asyncio.TimeoutError:
                    # Timeout is normal - just continue waiting for messages
                    continue
                except WebSocketDisconnect:
                    logger.info(f"[{self.connection_id}] WebSocket disconnected")
                    break
                except Exception as e:
                    logger.error(f"[{self.connection_id}] Error in message processing: {e}")
                    break

        finally:
            # Cancel background tasks
            if relay_task and not relay_task.done():
                relay_task.cancel()
            if health_task and not health_task.done():
                health_task.cancel()
            try:
                await relay_task
                await health_task
            except asyncio.CancelledError:
                pass

async def handle_browser_session(websocket: WebSocket):
    """
    **FIXED** browser WebSocket connection handler with proper protocol.

    Protocol:
    1. Client connects to /voice/browser
    2. Server **IMMEDIATELY** sends {"type": "connected", ...}
    3. Client responds with {"type": "client_ready", ...}
    4. Server acknowledges with {"type": "client_handshake_ack", ...}
    5. Both sides exchange audio (binary) and JSON messages
    6. Either side closes the connection

    The browser widget should also:
    1. Send client_ready message when onopen fires
    2. Handle all incoming message types (audio, text, heartbeat)
    """
    connection = FixedBrowserWebSocketConnection(websocket)

    try:
        # Step 1: Accept connection
        await connection.accept_connection()

        # Step 2: Send IMMEDIATE connection ready (server-initiated)
        await connection.send_immediate_connection_ready()

        # Step 3: Setup Gemini session
        if not await connection.setup_gemini_session():
            logger.error(f"[{connection.connection_id}] Failed to setup Gemini session, closing connection")
            return

        # Step 4: Start response relay and health monitor
        relay_task = await connection.start_relay_tasks()
        health_task = await connection.start_health_monitor()

        # Step 5: Wait for messages from browser
        await connection.wait_for_messages(relay_task, health_task)

    except WebSocketDisconnect:
        logger.info(f"[{connection.connection_id}] Browser WebSocket disconnected")
    except Exception as e:
        logger.error(f"[{connection.connection_id}] Browser bridge error: {e}", exc_info=True)
    finally:
        # Cleanup
        logger.info(f"[{connection.connection_id}] Cleaning up connection")
        await connection.close()
        logger.info(f"[{connection.connection_id}] Browser session ended")

# Export the fixed function for main.py
__all__ = ["handle_browser_session"]
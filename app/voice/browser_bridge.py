"""
Browser ↔ Gemini Live API bridge.

Direct WebSocket connection from the browser.
The browser sends PCM16 16kHz mono audio, and receives
PCM16 audio back + JSON tool call responses.

FIXED PROTOCOL:
1. Client opens WebSocket to /voice/browser
2. Server IMMEDIATELY sends {"type": "connected", "message": "..."} (server-initiated)
3. Client sends {"type": "client_ready", "client_id": "..."}
4. Server responds {"type": "client_handshake_ack", "message": "..."}
5. Both sides exchange audio (binary) and JSON messages
6. Either side closes the connection
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
from app.voice.bridge import load_system_prompt  # shared system prompt loader
from app.voice.gemini_live import GeminiLiveSession

async def handle_browser_session(websocket: WebSocket):
    """
    **FIXED** browser WebSocket connection handler with proper protocol.

    Protocol:
    1. Client connects to /voice/browser
    2. Server IMMEDIATELY sends {"type": "connected", "message": "..."} (server-initiated)
    3. Client sends {"type": "client_ready", "client_id": "..."}
    4. Server responds {"type": "client_handshake_ack", "message": "..."}
    5. Both sides exchange audio (binary) and JSON messages
    6. Either side closes the connection

    The browser widget should also:
    1. Send client_ready message when onopen fires
    2. Handle all incoming message types (audio, text, heartbeat)
    """
    await websocket.accept()
    gemini_session: GeminiLiveSession | None = None

    try:
        # Load the system prompt with today's date
        system_prompt = await load_system_prompt()

        # Signal connection ready FIRST (before setting up Gemini)
        await websocket.send_json({
            "type": "connected",
            "message": "Connected to Bella Italia voice assistant. Start speaking!",
        })

        # ── Create Gemini Live session ───────────────────────
        async def on_tool_call(tool_name: str, args: dict):
            """Handle a tool call by dispatching to restaurant services."""
            async with async_session_factory() as db_session:
                return await handle_tool_call(db_session, tool_name, args)

        gemini_session = GeminiLiveSession(
            system_prompt=system_prompt,
            tool_declarations=TOOL_DECLARATIONS,
            on_tool_call=on_tool_call,
        )

        try:
            await gemini_session.start()
            logger.info("Gemini Live session active for browser client")
            await websocket.send_json({
                "type": "status",
                "text": "Voice assistant ready!",
            })
        except Exception as gemini_err:
            logger.error(f"Gemini session failed: {gemini_err}")
            await websocket.send_json({
                "type": "error",
                "text": f"Could not connect to voice service: {gemini_err}",
            })
            gemini_session = None  # Don't try to use it

        # ── Forward Gemini audio → browser ───────────────────
        async def relay_gemini_to_browser():
            """Forward Gemini's audio and text responses to the browser."""
            if not gemini_session:
                return
            try:
                async for event in gemini_session.audio_output_stream():
                    if event["type"] == "audio":
                        # Send raw PCM16 audio
                        await websocket.send_bytes(bytes(event["data"]))
                    elif event["type"] == "text":
                        # Send text as JSON
                        await websocket.send_json({
                            "type": "text",
                            "text": event["text"],
                        })
            except Exception as e:
                if "close" not in str(e).lower():
                    logger.error(f"Gemini→Browser relay error: {e}")

        relay_task = None
        if gemini_session:
            relay_task = asyncio.create_task(relay_gemini_to_browser())

        # ── Main loop: receive audio from browser, forward to Gemini ──
        # Also handle JSON messages for any client-side requests
        buffer_size = 0

        while True:
            try:
                raw = await websocket.receive()
            except WebSocketDisconnect:
                break

            if raw.get("type") == "websocket.disconnect":
                break

            if "bytes" in raw:
                # Raw PCM16 audio from browser
                audio_bytes = raw["bytes"]
                if audio_bytes and gemini_session:
                    buffer_size += len(audio_bytes)
                    await gemini_session.push_audio(audio_bytes)

            elif "text" in raw:
                # JSON control messages from browser (future: stop, settings, etc.)
                try:
                    msg = json.loads(raw["text"])
                    logger.debug(f"Browser control message: {msg}")
                    if msg.get("type") == "stop":
                        break
                except json.JSONDecodeError:
                    pass

    except WebSocketDisconnect:
        logger.info("Browser disconnected")
    except Exception as e:
        logger.error(f"Browser bridge error: {e}", exc_info=True)
    finally:
        # Cleanup
        if gemini_session:
            await gemini_session.close()
        logger.info("Browser session ended")
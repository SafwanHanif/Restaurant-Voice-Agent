"""
LiveKit WebRTC bridge for browser-based voice.

Customers can speak to the AI receptionist from the restaurant website
via a browser widget. LiveKit handles WebRTC; this module bridges
LiveKit audio tracks ↔ Gemini Live API sessions.

Same backend as the Twilio path — just a different audio source.
"""

import asyncio
from datetime import date

from livekit import rtc
from loguru import logger

from app.database import async_session_factory
from app.tools.definitions import TOOL_DECLARATIONS, handle_tool_call
from app.voice.audio import silence
from app.voice.bridge import load_system_prompt
from app.voice.gemini_live import GeminiLiveSession


async def handle_livekit_room(room_name: str, participant_name: str, audio_track: rtc.AudioTrack):
    """
    Process a LiveKit participant's audio and bridge it to Gemini.
    Called when a user connects via the restaurant website widget.
    """
    logger.info(f"LiveKit session started: room={room_name}, participant={participant_name}")

    gemini_session: GeminiLiveSession | None = None

    try:
        # Load the system prompt
        system_prompt = await load_system_prompt()

        # Create the Gemini session
        async def on_tool_call(tool_name: str, args: dict):
            async with async_session_factory() as db_session:
                return await handle_tool_call(db_session, tool_name, args)

        gemini_session = GeminiLiveSession(
            system_prompt=system_prompt,
            tool_declarations=TOOL_DECLARATIONS,
            on_tool_call=on_tool_call,
        )

        await gemini_session.start()
        logger.info(f"Gemini Live session active for LiveKit participant {participant_name}")

        # Set up audio forwarding
        audio_source = rtc.AudioSource(16000, 1)  # 16kHz, mono

        async def forward_user_audio():
            """Forward user's microphone audio to Gemini."""
            async for frame in audio_track:
                # AudioTrack yields rtc.AudioFrame — convert to bytes
                pcm16_bytes = frame.data.tobytes()
                await gemini_session.push_audio(pcm16_bytes)

        async def forward_gemini_audio():
            """Forward Gemini's spoken response back to the user's browser."""
            async for event in gemini_session.audio_output_stream():
                if event["type"] == "audio":
                    # Gemini sends PCM16 16kHz — pass directly to LiveKit
                    audio_frame = rtc.AudioFrame(
                        data=bytes(event["data"]),
                        sample_rate=16000,
                        num_channels=1,
                        samples_per_channel=len(event["data"]) // 2,
                    )
                    await audio_source.capture_frame(audio_frame)
                elif event["type"] == "text":
                    logger.debug(f"[Gemini] {event['text']}")

        # Run both directions concurrently
        await asyncio.gather(
            forward_user_audio(),
            forward_gemini_audio(),
        )

    except Exception as e:
        logger.error(f"Error in LiveKit bridge: {e}", exc_info=True)
    finally:
        if gemini_session:
            await gemini_session.close()
        logger.info(f"LiveKit session ended: {participant_name}")

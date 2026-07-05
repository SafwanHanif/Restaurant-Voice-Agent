"""
Handles real inbound phone calls via Twilio.

Flow:
1. Twilio hits POST /twilio/incoming-call when someone dials the restaurant's
   number. We reply with TwiML that opens a bidirectional Media Stream.
2. Twilio connects to wss://.../twilio/media-stream and starts sending
   base64-encoded mulaw/8kHz audio frames as JSON "media" events.
3. We decode mulaw->PCM16, resample 8kHz->16kHz, and feed it to a
   GeminiVoiceSession. Gemini's PCM16/24kHz audio comes back, gets resampled
   to 8kHz and re-encoded to mulaw, and is sent back to Twilio the same way.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import uuid

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response

from audio_utils import mulaw_to_pcm16, pcm16_to_mulaw, resample_pcm16
from config import PUBLIC_BASE_URL
from gemini_session import GeminiVoiceSession

logger = logging.getLogger("voice_agent")
router = APIRouter()


@router.post("/twilio/incoming-call")
async def incoming_call(request: Request):
    """Twilio webhook - point your Twilio phone number's Voice webhook here."""
    if not PUBLIC_BASE_URL:
        return Response(
            content="<Response><Say>Server misconfigured: PUBLIC_BASE_URL not set.</Say></Response>",
            media_type="application/xml",
        )
    ws_url = PUBLIC_BASE_URL.replace("https://", "wss://").replace("http://", "ws://")
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{ws_url}/twilio/media-stream" />
    </Connect>
</Response>"""
    return Response(content=twiml, media_type="application/xml")


@router.websocket("/twilio/media-stream")
async def media_stream(websocket: WebSocket):
    await websocket.accept()
    session_id = uuid.uuid4().hex[:12]
    stream_sid: str | None = None
    caller_number = ""

    audio_in_queue: asyncio.Queue[bytes | None] = asyncio.Queue()

    async def send_to_twilio(pcm24k_bytes: bytes):
        nonlocal stream_sid
        if stream_sid is None:
            return
        pcm8k = resample_pcm16(pcm24k_bytes, 24000, 8000)
        mulaw = pcm16_to_mulaw(pcm8k)
        payload = base64.b64encode(mulaw).decode("ascii")
        await websocket.send_text(
            json.dumps({"event": "media", "streamSid": stream_sid, "media": {"payload": payload}})
        )

    gemini_task: asyncio.Task | None = None

    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            event = msg.get("event")

            if event == "start":
                stream_sid = msg["start"]["streamSid"]
                caller_number = msg["start"].get("customParameters", {}).get("from", "")
                session = GeminiVoiceSession(session_id, channel="phone", caller_number=caller_number)
                gemini_task = asyncio.create_task(session.run(send_to_twilio, audio_in_queue))
                logger.info("[%s] Twilio call started, stream=%s", session_id, stream_sid)

            elif event == "media":
                mulaw_bytes = base64.b64decode(msg["media"]["payload"])
                pcm8k = mulaw_to_pcm16(mulaw_bytes)
                pcm16k = resample_pcm16(pcm8k, 8000, 16000)
                await audio_in_queue.put(pcm16k)

            elif event == "stop":
                logger.info("[%s] Twilio call ended", session_id)
                break

    except WebSocketDisconnect:
        logger.info("[%s] Twilio websocket disconnected", session_id)
    finally:
        await audio_in_queue.put(None)
        if gemini_task:
            await gemini_task

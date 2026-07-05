"""
Wraps a Gemini Live API session. This class is transport-agnostic: it
doesn't know or care whether audio came from Twilio or a browser mic - it
just accepts 16kHz PCM16 bytes in and emits 24kHz PCM16 bytes out via a
callback. twilio_routes.py and web_routes.py each do their own format
conversion before/after talking to this class.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

from google import genai
from google.genai import types

from config import GEMINI_API_KEY, GEMINI_MODEL, GEMINI_VOICE, RESTAURANT_NAME, RESTAURANT_HOURS
from db import CallLog, get_db
from tools import FUNCTION_DECLARATIONS, execute_tool

logger = logging.getLogger("voice_agent")

SYSTEM_INSTRUCTION = f"""You are the AI host answering the phone and web chat for \
{RESTAURANT_NAME}, a real restaurant. Hours: {RESTAURANT_HOURS}.

Your job: take reservations, take food orders, and answer menu/hours questions,
speaking naturally like a friendly, efficient host - not a script reader.

Rules you must follow:
- Always use your tools for real data (menu, availability, hours). Never invent
  menu items, prices, or availability from your own knowledge.
- Before booking a table, call check_availability. Only call create_reservation
  after you have the customer's name, phone number, party size, date and time.
- When taking a food order, add each item with add_item_to_order as the
  customer mentions it, read the full order back to confirm before calling
  place_order, and get their name, phone number, and pickup/delivery choice.
- Keep responses short and conversational - this is a live voice call, not a
  text chat. Don't list more than 4-5 menu items out loud at once; ask what
  they're interested in instead of reciting the whole menu.
- If the caller is upset, asks for a manager, wants something you can't do
  (large parties of 8+, catering, complaints), or the conversation goes
  somewhere you're not confident about, call transfer_to_human immediately.
- Confirm details back to the caller before finalizing anything (reservation
  or order) since you can't undo a mistake as easily as a human host can.
"""

AudioSink = Callable[[bytes], Awaitable[None]]
EventSink = Callable[[dict], Awaitable[None]]


async def _noop_event(_event: dict) -> None:
    return None


class GeminiVoiceSession:
    """One phone/web call = one instance of this class."""

    def __init__(self, session_id: str, channel: str, caller_number: str = ""):
        self.session_id = session_id
        self.channel = channel
        self.caller_number = caller_number
        self._client = genai.Client(api_key=GEMINI_API_KEY)
        self._session = None
        self._closed = False
        self.transcript_lines: list[str] = []

    async def run(
        self,
        on_audio_out: AudioSink,
        audio_in_queue: asyncio.Queue[bytes | None],
        on_event: EventSink = _noop_event,
    ):
        """
        Connects to Gemini Live and runs two concurrent loops:
        - sender: drains audio_in_queue -> Gemini
        - receiver: Gemini responses -> on_audio_out callback, plus tool calls
        A None on audio_in_queue signals the call ended.
        """
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=types.Content(parts=[types.Part(text=SYSTEM_INSTRUCTION)]),
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=GEMINI_VOICE)
                )
            ),
            tools=[{"function_declarations": FUNCTION_DECLARATIONS}],
            input_audio_transcription={},
            output_audio_transcription={},
        )

        db = get_db()
        db.add(CallLog(id=self.session_id, channel=self.channel, caller_number=self.caller_number))
        db.commit()

        try:
            async with self._client.aio.live.connect(model=GEMINI_MODEL, config=config) as session:
                self._session = session
                logger.info("[%s] connected to Gemini Live", self.session_id)
                await asyncio.gather(
                    self._sender_loop(audio_in_queue),
                    self._receiver_loop(on_audio_out, on_event, db),
                )
        except Exception:
            logger.exception("[%s] Gemini Live session error", self.session_id)
        finally:
            logger.info("[%s] session ended", self.session_id)
            self._save_transcript(db)
            db.close()

    async def _sender_loop(self, audio_in_queue: asyncio.Queue[bytes | None]):
        """Send mic audio to Gemini continuously. Runs until None sentinel."""
        chunk_count = 0
        while True:
            chunk = await audio_in_queue.get()
            if chunk is None:
                logger.info("[%s] sender loop: got None sentinel, exiting", self.session_id)
                break
            chunk_count += 1
            try:
                await self._session.send_realtime_input(
                    audio=types.Blob(data=chunk, mime_type="audio/pcm;rate=16000")
                )
            except Exception:
                logger.exception("[%s] sender loop: send_realtime_input failed (chunk %d)", self.session_id, chunk_count)
                break
        logger.info("[%s] sender loop: sent %d total chunks", self.session_id, chunk_count)
        self._closed = True

    async def _receiver_loop(self, on_audio_out: AudioSink, on_event: EventSink, db):
        """
        Receive responses from Gemini Live.

        In google-genai >=2.0, session.receive() yields messages for one
        turn and then exits when turn_complete is signaled. We wrap it in
        an outer loop so the conversation continues across multiple turns.
        """
        turn_count = 0
        while not self._closed:
            turn_count += 1
            logger.info("[%s] receiver: starting turn %d", self.session_id, turn_count)
            try:
                async for response in self._session.receive():
                    if self._closed:
                        break

                    server_content = response.server_content
                    if server_content:
                        # Barge-in: caller interrupted the model
                        if server_content.interrupted:
                            logger.info("[%s] barge-in detected", self.session_id)
                            await on_event({"type": "interrupted"})
                        # Caller transcription
                        if server_content.input_transcription and server_content.input_transcription.text:
                            text = server_content.input_transcription.text
                            self.transcript_lines.append(f"Caller: {text}")
                            await on_event({"type": "transcript", "speaker": "caller", "text": text})
                        # Agent transcription
                        if server_content.output_transcription and server_content.output_transcription.text:
                            text = server_content.output_transcription.text
                            self.transcript_lines.append(f"Agent: {text}")
                            await on_event({"type": "transcript", "speaker": "agent", "text": text})

                    # Audio data (works as a property in google-genai >=2.0)
                    if response.data:
                        await on_audio_out(response.data)

                    # Tool call
                    if response.tool_call:
                        await self._handle_tool_call(response.tool_call, db, on_event)

            except Exception as exc:
                logger.error("[%s] receiver: receive() error: %s", self.session_id, exc)
                break

        logger.info("[%s] receiver: stopped after %d turns", self.session_id, turn_count)

    async def _handle_tool_call(self, tool_call, db, on_event: EventSink):
        function_responses = []
        for fc in tool_call.function_calls:
            args = dict(fc.args or {})
            try:
                result = await asyncio.to_thread(execute_tool, self.session_id, db, fc.name, args)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Tool %s failed", fc.name)
                result = {"success": False, "reason": str(exc)}
            await on_event({"type": "tool_call", "name": fc.name, "args": args, "result": result})
            function_responses.append(
                types.FunctionResponse(name=fc.name, id=fc.id, response=result)
            )
        await self._session.send_tool_response(function_responses=function_responses)

    def _save_transcript(self, db):
        log = db.query(CallLog).filter(CallLog.id == self.session_id).first()
        if log:
            log.transcript = "\n".join(self.transcript_lines)
            import datetime as dt
            log.ended_at = dt.datetime.utcnow()
            db.commit()

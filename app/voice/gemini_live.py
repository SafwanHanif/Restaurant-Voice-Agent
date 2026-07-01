"""
Gemini Live API session management.

This module handles the bidirectional WebSocket connection to Gemini Live API,
sending audio via `send_realtime_input` and receiving audio + tool call responses.

Key concepts:
- One Gemini Live session = one phone call / browser session
- Audio is sent in real-time chunks via `send_realtime_input`
- Gemini sends back audio data AND tool_call commands
- Tool call results are sent back via `send_tool_response`
"""

import asyncio
from typing import Any, AsyncIterator, Callable

from google import genai
from google.genai import types as genai_types
from loguru import logger

from app.config import settings


# Gemini Live model — supports AUDIO in/out + function calling
LIVE_MODEL = "gemini-2.5-flash-native-audio-latest"


class GeminiLiveSession:
    """
    Manages a single Gemini Live API session.

    Usage:
        session = GeminiLiveSession(system_prompt, tool_decls, on_tool_call)
        await session.start()
        await session.push_audio(audio_bytes)
        async for event in session.audio_output_stream(): ...
        await session.close()
    """

    def __init__(
        self,
        system_prompt: str,
        tool_declarations: list[dict],
        on_tool_call: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None,
    ):
        self.system_prompt = system_prompt
        self.tool_declarations = tool_declarations
        self.on_tool_call = on_tool_call
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.session: genai_types.LiveClientSession | None = None
        self._connect_cm = None  # stored async context manager
        self._running = False
        self._audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        self._output_queue: asyncio.Queue[dict | None] = asyncio.Queue()

    async def start(self):
        """Open the Gemini Live session and start send/receive loops."""
        config = {
            "response_modalities": ["AUDIO"],
            "system_instruction": {"parts": [{"text": self.system_prompt}]},
            "tools": [{"function_declarations": self.tool_declarations}],
        }

        logger.info(f"Starting Gemini Live session (model={LIVE_MODEL})...")

        # connect() returns an async context manager in SDK v2.10+
        cm = self.client.aio.live.connect(model=LIVE_MODEL, config=config)
        self._connect_cm = cm
        self.session = await cm.__aenter__()

        self._running = True

        # Start concurrent send/receive loops
        self._send_task = asyncio.create_task(self._send_loop())
        self._recv_task = asyncio.create_task(self._recv_loop())

        logger.info("Gemini Live session started")

    async def push_audio(self, audio_chunk: bytes):
        """Queue audio data to send to Gemini via send_realtime_input."""
        await self._audio_queue.put(audio_chunk)

    def audio_output_stream(self) -> AsyncIterator[dict]:
        """
        Async iterator that yields events:
            {"type": "audio", "data": bytes}     — PCM16 audio from Gemini
            {"type": "text", "text": str}        — model text (for logging/debug)
            {"type": "tool_call", ...}            — handled internally
        """
        class _Stream:
            def __init__(self, q):
                self._q = q
            def __aiter__(self):
                return self
            async def __anext__(self):
                item = await self._q.get()
                if item is None:
                    raise StopAsyncIteration
                return item
        return _Stream(self._output_queue)

    async def close(self):
        """Gracefully shut down the session."""
        self._running = False
        logger.info("Closing Gemini Live session...")
        await self._audio_queue.put(None)

        # Clean up send/receive tasks
        for attr in ["_send_task", "_recv_task"]:
            task = getattr(self, attr, None)
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass

        # Exit the async context manager (cleanly closes the session)
        if self._connect_cm:
            try:
                await self._connect_cm.__aexit__(None, None, None)
            except Exception:
                pass
            self._connect_cm = None

        self.session = None
        logger.info("Gemini Live session closed.")

    # ── Internal: send loop ─────────────────────────────────

    async def _send_loop(self):
        """Continuously send queued audio to Gemini via send_realtime_input."""
        try:
            while self._running:
                chunk = await self._audio_queue.get()
                if chunk is None:
                    break
                try:
                    # SDK v2.10+: audio is wrapped in a Blob with correct mime type
                    audio_blob = genai_types.Blob(
                        data=chunk,
                        mime_type="audio/pcm;rate=16000",
                    )
                    await self.session.send_realtime_input(audio=audio_blob)
                except Exception as e:
                    logger.error(f"Error sending audio to Gemini: {e}")
                    break
        except asyncio.CancelledError:
            pass

    # ── Internal: receive loop ──────────────────────────────

    async def _recv_loop(self):
        """Continuously receive responses from Gemini."""
        try:
            async for response in self.session.receive():
                if not self._running:
                    break

                # --- Audio data from Gemini (inside server_content.model_turn parts) ---
                if response.server_content and response.server_content.model_turn:
                    for part in response.server_content.model_turn.parts:
                        # Audio comes as inline_data (Blob)
                        if part.inline_data and part.inline_data.data:
                            await self._output_queue.put({
                                "type": "audio",
                                "data": part.inline_data.data,
                            })
                        # Text responses
                        if part.text:
                            logger.debug(f"Gemini: {part.text}")
                            await self._output_queue.put({
                                "type": "text",
                                "text": part.text,
                            })

                # --- Tool call from Gemini ---
                if response.tool_call:
                    for fc in response.tool_call.function_calls:
                        tool_name = fc.name
                        tool_args = dict(fc.args) if fc.args else {}
                        logger.info(f"Tool call: {tool_name}({tool_args})")

                        # Execute tool call (non-blocking)
                        if self.on_tool_call:
                            result = await self.on_tool_call(tool_name, tool_args)
                        else:
                            result = {"error": "No tool handler configured"}

                        # Send result back via send_tool_response
                        try:
                            await self.session.send_tool_response(
                                function_responses=[genai_types.FunctionResponse(
                                    id=fc.id,
                                    name=tool_name,
                                    response={"result": result},
                                )]
                            )
                        except Exception as e:
                            logger.error(f"Error sending tool response: {e}")

                # --- Setup complete ---
                if response.setup_complete:
                    logger.info(f"Session setup complete: {response.setup_complete.session_id}")

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in Gemini receive loop: {e}")
        finally:
            await self._output_queue.put(None)

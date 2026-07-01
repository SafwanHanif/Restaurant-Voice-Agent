"""
Test script to verify browser WebSocket voice connection with Gemini Live API.
This simulates what the browser VoiceWidget does.
"""

import asyncio
import json
import websockets
from loguru import logger
from app.main import app
from app.voice.gemini_live import GeminiLiveSession
from app.tools.definitions import TOOL_DECLARATIONS
from app.voice.bridge import load_system_prompt

logger.remove()
logger.add("test_browser.log", rotation="10 MB")

class TestBrowserClient:
    def __init__(self, host="localhost", port=8000):
        self.host = host
        self.port = port
        self.uri = f"ws://{host}:{port}/voice/browser"
        self.websocket = None
        self.gemini_session = None

    async def connect(self):
        """Connect to the browser WebSocket endpoint and start the flow."""
        try:
            # Try to connect with a short timeout and retry logic
            for attempt in range(3):
                try:
                    self.websocket = await asyncio.wait_for(
                        websockets.connect(self.uri),
                        timeout=2.0
                    )
                    logger.info(f"Connected to browser WebSocket on attempt {attempt + 1}: {self.uri}")
                    return True
                except (websockets.exceptions.ConnectionClosed, OSError) as e:
                    if attempt < 2:
                        logger.warning(f"Connection attempt {attempt + 1} failed: {e}, retrying...")
                        await asyncio.sleep(1)
                    else:
                        raise e
            return False
        except Exception as e:
            logger.error(f"Failed to connect to browser WebSocket after retries: {e}")
            return False

    async def start_gemini_session(self):
        """Create and start a Gemini Live session for testing."""
        try:
            system_prompt = await load_system_prompt()

            async def on_tool_call(tool_name: str, args: dict):
                logger.info(f"Tool call from Gemini: {tool_name}({args})")
                # For testing, return a mock result for check_availability
                if tool_name == "check_availability":
                    return {"available": True, "message": "We have tables available: Table #1 — seats 2; Table #2 — seats 4", "tables": [{"table_number": 1, "capacity": 2, "location": "Window"}, {"table_number": 2, "capacity": 4, "location": "Corner"}]}
                return {"error": f"Tool {tool_name} not implemented in test"}

            self.gemini_session = GeminiLiveSession(
                system_prompt=system_prompt,
                tool_declarations=TOOL_DECLARATIONS,
                on_tool_call=on_tool_call,
            )
            await self.gemini_session.start()
            logger.info("Gemini Live session started")
            return True
        except Exception as e:
            logger.error(f"Failed to start Gemini session: {e}")
            return False

    async def send_text(self, text):
        """Send text control message to WebSocket."""
        if self.websocket and self.websocket.open:
            await self.websocket.send(text)
            logger.info(f"Sent text message: {text}")

    async def receive_messages(self):
        """Receive and process WebSocket messages."""
        if not self.websocket:
            return

        async for message in self.websocket:
            try:
                if isinstance(message, bytes):
                    # Audio data from Gemini
                    logger.info(f"Received {len(message)} bytes of audio from Gemini")
                    if self.gemini_session:
                        # In real flow, browser would play this audio
                        pass
                else:
                    # Text message (JSON)
                    msg_data = json.loads(message)
                    logger.info(f"Received JSON: {json.dumps(msg_data, indent=2)}")
                    if msg_data.get("type") == "connected":
                        logger.info(f"Connection confirmed: {msg_data.get('message')}")
                    elif msg_data.get("type") == "text":
                        logger.info(f"Transcript: {msg_data.get('text')}")
            except json.JSONDecodeError:
                logger.info(f"Received non-JSON text: {message}")
            except Exception as e:
                logger.error(f"Error processing message: {e}")

    async def send_test_audio_chunk(self):
        """Send a test audio chunk to simulate browser input."""
        if self.websocket and self.websocket.open:
            # Create a silent audio chunk (1 channel, 320 samples = 20ms of silence)
            # Sample rate is 16kHz, so 20ms = 320 samples
            test_chunk = bytes([0] * 320 * 2)  # 16-bit samples
            await self.websocket.send(test_chunk)
            logger.info(f"Sent {len(test_chunk)} bytes of test audio (silence)")

    async def run_test(self):
        """Run the complete browser voice test."""
        if not await self.connect():
            return False

        # Start Gemini session
        if not await self.start_gemini_session():
            return False

        # Signal connection ready (as the server expects this)
        await self.send_text(json.dumps({
            "type": "connected",
            "message": "Test client connected"
        }))

        # Start listening for messages in background
        receiver_task = asyncio.create_task(self.receive_messages())

        # Simulate browser sending audio
        await self.send_test_audio_chunk()

        # Wait for a bit to see responses
        await asyncio.sleep(3)

        # Send a second audio chunk
        await self.send_test_audio_chunk()

        # Wait a bit more
        await asyncio.sleep(3)

        # Send a text control message
        await self.send_text(json.dumps({
            "type": "stop"
        }))

        # Clean up
        receiver_task.cancel()
        try:
            await self.gemini_session.close()
        except:
            pass
        if self.websocket:
            await self.websocket.close()

        logger.info("Test completed")
        return True

async def main():
    """Run the browser voice test."""
    test_client = TestBrowserClient()
    success = await test_client.run_test()
    if success:
        print("[OK] Browser voice test completed successfully!")
    else:
        print("[FAIL] Browser voice test failed")

if __name__ == "__main__":
    asyncio.run(main())
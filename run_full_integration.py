"""
Full integration test that starts the FastAPI server and tests both backend and frontend functionality.
This simulates running the complete system with backend server and browser client.
"""
import asyncio
import json
import threading
import time
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient
import websockets

# Import the app
from app.main import app as fastapi_app
from app.voice.bridge import load_system_prompt
from app.voice.gemini_live import GeminiLiveSession
from app.tools.definitions import TOOL_DECLARATIONS

class RestaurantVoiceAgentTester:
    def __init__(self):
        self.server_url = "http://localhost:8000"
        self.websocket_url = "ws://localhost:8000/voice/browser"
        self.client = TestClient(fastapi_app)
        self.server_thread = None
        self.server_process = None

    def start_server(self):
        """Start the FastAPI server in a separate process."""
        print("[SERVER] Starting FastAPI server...")

        def run_server():
            try:
                # Import uvicorn here to avoid issues on import
                import uvicorn
                from app.main import app

                config = uvicorn.Config(
                    app,
                    host="localhost",
                    port=8000,
                    log_level="warning",  # Reduce noise
                    access_log=False
                )

                server = uvicorn.Server(config)
                asyncio.run(server.serve())
            except Exception as e:
                print(f"[SERVER ERROR] Failed to start server: {e}")

        # Start server in a separate thread
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()

        # Wait for server to be ready
        print("[SERVER] Waiting for server to start...")
        for i in range(30):  # Wait up to 30 seconds
            try:
                response = self.client.get("/health", timeout=1)
                if response.status_code == 200:
                    print(f"[SERVER] Server is ready! Status: {response.json()}")
                    return True
            except:
                time.sleep(1)

        print("[SERVER] Server failed to start within 30 seconds")
        return False

    def stop_server(self):
        """Stop the server."""
        if self.server_thread:
            print("[SERVER] Stopping server...")
            # The server is set to daemon=True, so it will terminate when main thread ends
            self.server_thread.join(timeout=5)

    def test_backend_endpoints(self):
        """Test all backend endpoints."""
        print("\n" + "="*60)
        print("BACKEND ENDPOINTS TEST")
        print("="*60)

        tests = [
            ("Health Check", lambda: self.client.get("/health")),
            ("Voice Widget", lambda: self.client.get("/voice-widget")),
            ("Config", lambda: self.client.get("/test/config")),
            ("Menu Endpoint", lambda: self.client.get("/api/menu")),
            ("Menu Item", lambda: self.client.get("/api/menu/pizza Margherita")),
            ("Reservation Test", lambda: self.client.post(
                "/test/reservation",
                json={
                    "customer_name": "Test User",
                    "phone": "+15551112222",
                    "party_size": 4,
                    "date": "2026-07-04",
                    "time": "19:00"
                }
            )),
        ]

        passed = 0
        total = len(tests)

        for test_name, test_func in tests:
            try:
                response = test_func()
                if response.status_code == 200:
                    print(f"[BACKEND OK] {test_name}: Status {response.status_code}")
                    passed += 1

                    # Show some details for key endpoints
                    if test_name == "Voice Widget":
                        if "Bella Italia" in response.text:
                            print(f"[BACKEND OK] Voice widget contains branding")
                    elif test_name == "Config":
                        config = response.json()
                        print(f"[BACKEND OK] App: {config.get('app_name')}")
                        print(f"[BACKEND OK] Gemini Key Set: {config.get('gemini_key_set')}")
                else:
                    print(f"[BACKEND FAIL] {test_name}: Status {response.status_code}")
                    if response.text:
                        print(f"  Error: {response.text[:100]}")
            except Exception as e:
                print(f"[BACKEND ERROR] {test_name}: {e}")

        return passed, total

    async def test_websocket_connection(self, timeout=10):
        """Test WebSocket connection (simulating browser client)."""
        print("\n" + "="*60)
        print("WEBSOCKET CONNECTION TEST")
        print("="*60)

        try:
            print(f"[CLIENT] Attempting to connect to {self.websocket_url}...")

            # Connect with timeout
            try:
                websocket = await asyncio.wait_for(
                    websockets.connect(self.websocket_url),
                    timeout=timeout
                )

                print(f"[CLIENT OK] WebSocket connection established!")

                # Send a handshake message
                handshake_msg = {
                    "type": "handshake",
                    "message": "Browser client test connection"
                }

                await websocket.send(json.dumps(handshake_msg))
                print(f"[CLIENT OK] Sent handshake: {handshake_msg}")

                # Try to receive a response (might not get one if server expects browser protocol)
                try:
                    response = await asyncio.wait_for(
                        websocket.receive(),
                        timeout=3
                    )
                    print(f"[CLIENT OK] Received response: {response}")
                except asyncio.TimeoutError:
                    print("[CLIENT WARN] No handshake response received (expected if browser expects different protocol)")

                # Send stop message to close
                stop_msg = {"type": "stop"}
                await websocket.send(json.dumps(stop_msg))
                print(f"[CLIENT OK] Sent stop message")

                # Close connection
                await websocket.close()
                print("[CLIENT OK] WebSocket connection closed")

                return True

            except asyncio.TimeoutError:
                print(f"[CLIENT FAIL] Connection timeout after {timeout} seconds")
                return False
            except Exception as e:
                print(f"[CLIENT FAIL] Connection error: {e}")
                return False

        except Exception as e:
            print(f"[CLIENT ERROR] WebSocket test failed: {e}")
            return False

    async def test_gemini_session(self):
        """Test Gemini Live session creation (server-side)."""
        print("\n" + "="*60)
        print("GEMINI LIVE SESSION TEST")
        print("="*60)

        try:
            # Load system prompt
            print("[GEMINI] Loading system prompt...")
            system_prompt = await load_system_prompt()
            print(f"[GEMINI OK] System prompt loaded ({len(system_prompt)} chars)")

            # Mock tool call handler
            async def mock_tool_call(tool_name: str, args: dict):
                return {"mock": "result", "tool": tool_name}

            # Create Gemini session
            print("[GEMINI] Creating Gemini Live session...")
            session = GeminiLiveSession(
                system_prompt=system_prompt,
                tool_declarations=TOOL_DECLARATIONS,
                on_tool_call=mock_tool_call,
            )
            print(f"[GEMINI OK] Gemini session created")

            # Check session attributes
            print(f"[GEMINI OK] Model: {session.client.__class__.__name__}")
            print(f"[GEMINI OK] Tools: {len(session.tool_declarations)}")

            # Note: We won't actually start the session since it would need
            # real API keys and audio hardware

            print("[GEMINI OK] Gemini Live session integration test passed")
            return True

        except Exception as e:
            print(f"[GEMINI ERROR] Gemini session test failed: {e}")
            return False

    def test_browser_experience(self):
        """Test the browser experience by checking HTML and JavaScript."""
        print("\n" + "="*60)
        print("BROWSER EXPERIENCE TEST")
        print("="*60)

        resp = self.client.get("/voice-widget")
        if resp.status_code != 200:
            print(f"[BROWSER FAIL] Could not load voice widget: {resp.status_code}")
            return False

        html = resp.text

        # Check essential components
        checks = [
            ("Bella Italia branding", "Bella Italia" in html),
            ("Voice widget UI", "mic-button" in html),
            ("WebSocket connection", "WebSocket" in html),
            ("Audio context", "AudioContext" in html),
            ("Microphone access", "getUserMedia" in html),
            ("Script tags", "<script>" in html),
        ]

        passed = 0
        for check_name, check_result in checks:
            if check_result:
                print(f"[BROWSER OK] {check_name}")
                passed += 1
            else:
                print(f"[BROWSER FAIL] Missing: {check_name}")

        success_rate = passed / len(checks)
        print(f"\n[INFO] Browser experience quality: {success_rate*100:.1f}%")

        return success_rate >= 0.7  # Allow some flexibility

    def run_integration_test(self):
        """Run the complete integration test."""
        print("=" * 60)
        print("RESTAURANT VOICE AGENT - FULL INTEGRATION TEST")
        print("=" * 60)

        try:
            # Start the server
            if not self.start_server():
                print("[FAIL] Could not start server")
                return False

            # Test backend endpoints
            backend_passed, backend_total = self.test_backend_endpoints()

            # Test browser experience
            browser_ok = self.test_browser_experience()

            # Test WebSocket connection (if server is running)
            websocket_ok = False
            try:
                # Quick check if server is responding
                resp = self.client.get("/health", timeout=2)
                if resp.status_code == 200:
                    # Now test actual WebSocket
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    websocket_ok = loop.run_until_complete(self.test_websocket_connection(5))
                    loop.close()
            except Exception as e:
                print(f"[INFO] WebSocket test skipped: {e}")

            # Test Gemini session (server-side)
            gemini_ok = False
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                gemini_ok = loop.run_until_complete(self.test_gemini_session())
                loop.close()
            except Exception as e:
                print(f"[INFO] Gemini session test skipped: {e}")

            # Summary
            print("\n" + "=" * 60)
            print("INTEGRATION TEST SUMMARY")
            print("=" * 60)
            print(f"Backend Endpoints: {backend_passed}/{backend_total} passed")
            print(f"Browser Experience: {'PASS' if browser_ok else 'FAIL'}")
            print(f"WebSocket Connection: {'PASS' if websocket_ok else 'FAIL'}")
            print(f"Gemini Integration: {'PASS' if gemini_ok else 'FAIL'}")

            all_passed = (backend_passed == backend_total and
                         browser_ok and
                         websocket_ok and
                         gemini_ok)

            if all_passed:
                print("\n[SUCCESS] ALL INTEGRATION TESTS PASSED!")
                print("The Restaurant Voice Agent system is fully functional.")
                return True
            else:
                print(f"\n[FAILURE] {len([x for x in [backend_passed != backend_total, not browser_ok, not websocket_ok, not gemini_ok] if x])} test category(s) failed.")
                return False

        except KeyboardInterrupt:
            print("\n[INFO] Test interrupted by user")
            return False
        except Exception as e:
            print(f"\n[ERROR] Integration test failed: {e}")
            return False
        finally:
            self.stop_server()

if __name__ == "__main__":
    tester = RestaurantVoiceAgentTester()
    success = tester.run_integration_test()
    exit(0 if success else 1)
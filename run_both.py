"""
Script to run both backend (FastAPI server) and simulate frontend (browser voice client).
"""
import asyncio
import json
import sys
import threading
import time
import websockets
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from app.main import app as fastapi_app

# Global variables to control the server
server_started = False
server_stopped = False

async def start_fastapi_server():
    """Start the FastAPI server in the background."""
    global server_started
    try:
        # Try to start the server
        from uvicorn import Config, Server

        config = Config(
            fastapi_app,
            host="localhost",
            port=8000,
            log_level="info",
            access_log=False
        )

        server = Server(config)
        # Run the server
        await server.serve()
        server_started = True
    except Exception as e:
        print(f"Error starting FastAPI server: {e}")
        server_started = False

async def test_browser_connection():
    """Test browser connection to the WebSocket endpoint."""
    print("\n" + "="*60)
    print("Testing browser WebSocket connection...")
    print("="*60)

    try:
        # Try to connect to the WebSocket endpoint
        uri = "ws://localhost:8000/voice/browser"
        print(f"Attempting to connect to {uri}...")

        # Set up connection with timeout
        connection_timeout = 5.0

        try:
            websocket = await asyncio.wait_for(
                websockets.connect(uri),
                timeout=connection_timeout
            )

            print("[OK] WebSocket connection established!")

            # Send a connection handshake message
            await websocket.send(json.dumps({
                "type": "handshake",
                "message": "Browser client testing connection"
            }))

            # Wait for a response
            try:
                response = await asyncio.wait_for(
                    websocket.receive(),
                    timeout=5.0
                )
                print(f"[OK] Received response: {response}")
            except asyncio.TimeoutError:
                print("[WARN] No response received within timeout")

            # Send a "stop" message to close cleanly
            await websocket.send(json.dumps({
                "type": "stop"
            }))

            # Close the connection
            await websocket.close()
            print("[OK] WebSocket closed cleanly")

            return True

        except asyncio.TimeoutError:
            print("[FAIL] Connection timeout after", connection_timeout, "seconds")
            return False
        except Exception as e:
            print(f"[FAIL] Connection failed: {e}")
            return False

    except Exception as e:
        print(f"[FAIL] Browser connection test failed: {e}")
        return False

async def simulate_browser_widget():
    """Simulate the browser widget behavior."""
    print("\n" + "="*60)
    print("Simulating browser VoiceWidget behavior...")
    print("="*60)

    from fastapi.testclient import TestClient

    client = TestClient(fastapi_app)

    # Test 1: Try to access the voice widget page
    print("Test 1: Accessing /voice-widget page...")
    resp = client.get("/voice-widget")
    if resp.status_code == 200:
        print("[OK] Voice widget page accessible")
        if "Bella Italia" in resp.text:
            print("[OK] Page contains expected branding")
        if "WebSocket" in resp.text:
            print("[OK] Page contains WebSocket configuration")
    else:
        print(f"[FAIL] Could not access voice widget: {resp.status_code}")
        return False

    # Test 2: Try health check
    print("\nTest 2: Health check...")
    resp = client.get("/health")
    if resp.status_code == 200:
        print(f"[OK] Health check: {resp.json()}")
    else:
        print(f"[FAIL] Health check failed: {resp.status_code}")
        return False

    # Test 3: Try config check
    print("\nTest 3: Configuration check...")
    resp = client.get("/test/config")
    if resp.status_code == 200:
        config = resp.json()
        print(f"[OK] Config check successful")
        print(f"   App: {config.get('app_name')}")
        print(f"   Gemini key set: {config.get('gemini_key_set')}")
    else:
        print(f"[FAIL] Config check failed: {resp.status_code}")
        return False

    return True

async def main():
    """Run the backend and frontend tests."""
    print("=" * 60)
    print("Restaurant Voice Agent - Full System Test")
    print("=" * 60)

    # Try to start the FastAPI server
    print("Attempting to start FastAPI server on port 8000...")
    try:
        # Start server in a separate task
        server_task = asyncio.create_task(start_fastapi_server())

        # Wait a bit for the server to start
        await asyncio.sleep(3)

        if server_started:
            print("[OK] FastAPI server started successfully")
        else:
            print("[WARN] Server may not have started properly")

        # Test browser connection
        browser_success = await test_browser_connection()

        # Simulate browser widget
        widget_success = await simulate_browser_widget()

        # Stop the server if it was running
        server_stopped = True
        print("\n[INFO] Stopping server...")

        # Cancel server task if still running
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass

        print("\n" + "=" * 60)
        print("FINAL RESULTS:")
        print("=" * 60)
        print(f"WebSocket Connection Test: {'PASS' if browser_success else 'FAIL'}")
        print(f"Frontend Widget Simulation: {'PASS' if widget_success else 'FAIL'}")

        if browser_success and widget_success:
            print("\n[SUCCESS] System test completed successfully!")
            print("The backend and frontend integration are working correctly.")
            return True
        else:
            print(f"\n[FAILURE] {('1' if not browser_success else '2') if not (browser_success and widget_success) else '0'} test(s) failed.")
            return False

    except Exception as e:
        print(f"\n[ERROR] System test failed with exception: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
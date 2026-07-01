"""
Script to diagnose WebSocket and browser bridge issues.
"""
import asyncio
import json
import websockets
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.main import app

def check_html_websocket_url():
    """Check what WebSocket URL is in the HTML."""
    print("CHECKING HTML WEBSOCKET URL")
    print("=" * 60)

    client = TestClient(app)
    resp = client.get("/voice-widget")

    if resp.status_code != 200:
        print(f"FAIL: Could not load HTML: {resp.status_code}")
        return

    html = resp.text

    # Find all ws:// occurrences
    import re
    ws_pattern = r'ws://[^\'"\s]*voice/browser'
    matches = re.findall(ws_pattern, html)

    print(f"Found {len(matches)} WebSocket URL(s) in HTML:")
    for i, match in enumerate(matches, 1):
        print(f"  {i}. {match}")

    # Also check for template literals
    if "${location.host}" in html:
        print("Found template literal: ${location.host}")
    if "location.host" in html:
        print("Found location.host reference")

    # Show some context around the WebSocket
    lines = html.split('\n')
    for i, line in enumerate(lines):
        if 'voice/browser' in line:
            start = max(0, i - 2)
            end = min(len(lines), i + 3)
            print(f"\nContext around WebSocket URL:")
            for j in range(start, end):
                marker = ">>>" if j == i else "   "
                print(f"{marker} Line {j}: {lines[j]}")

async def test_websocket_connection_detailed():
    """Test WebSocket connection with more detailed error information."""
    print("\n\nTESTING WEBSOCKET CONNECTION (DETAILED)")
    print("=" * 60)

    uri = "ws://localhost:8000/voice/browser"
    print(f"Attempting to connect to: {uri}")

    try:
        # Try to connect with verbose logging
        try:
            websocket = await asyncio.wait_for(
                websockets.connect(uri),
                timeout=5.0
            )

            print(f"SUCCESS: WebSocket connected")

            # Send a minimal valid message
            # The browser bridge expects a "type": "connected" message
            await websocket.send(json.dumps({
                "type": "connected",
                "message": "Test connection"
            }))

            print(f"Sent handshake message")

            # Try to receive response
            try:
                response = await asyncio.wait_for(
                    websocket.receive(),
                    timeout=3.0
                )
                print(f"Received response: {response}")
            except asyncio.TimeoutError:
                print(f"No response received (timeout)")

            await websocket.close()

        except asyncio.TimeoutError:
            print(f"Connection timeout after 5 seconds")

        except websockets.exceptions.InvalidURI as e:
            print(f"Invalid URI: {e}")

        except websockets.exceptions.InvalidHandshake as e:
            print(f"Invalid handshake: {e}")

        except websockets.exceptions.ConnectionClosed as e:
            print(f"Connection closed: {e}")

        except Exception as e:
            print(f"Connection error: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

    except Exception as e:
        print(f"Connection failed: {type(e).__name__}: {e}")

def analyze_browser_expectations():
    """Analyze what the browser expects."""
    print("\n\nANALYZING BROWSER EXPECTATIONS")
    print("=" * 60)

    client = TestClient(app)
    resp = client.get("/voice-widget")

    html = resp.text

    # Check JavaScript sections
    js_start = html.find('<script>')
    js_end = html.rfind('</script>') + 9

    if js_start != -1 and js_end != -1:
        javascript = html[js_start:js_end]

        # Extract key WebSocket code
        lines = javascript.split('\n')
        for i, line in enumerate(lines):
            if 'WebSocket' in line or 'ws://' in line:
                print(f"JavaScript line {i}: {line.strip()}")

        # Look for the main WebSocket initialization
        if 'const WS_URL' in javascript:
            print("\nFound WS_URL variable definition")

        # Look for the onopen event
        if 'ws.onopen' in javascript:
            print("Found WebSocket onopen handler")

        # Look for audio processing
        if 'onaudioprocess' in javascript:
            print("Found AudioContext onaudioprocess handler")

        # Look for the send function
        if 'ws.send' in javascript:
            print("Found WebSocket send function")

    print("\nBrowser widget should:")
    print("1. Connect to WS_URL when microphone button is clicked")
    print("2. Send PCM16 audio data to server")
    print("3. Receive PCM16 audio from server for playback")
    print("4. Display transcripts from server")
    print("5. Handle connection errors gracefully")

async def main():
    await check_html_websocket_url()
    await test_websocket_connection_detailed()
    analyze_browser_expectations()

if __name__ == "__main__":
    asyncio.run(main())
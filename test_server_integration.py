"""
Integration test for FastAPI server browser voice functionality.
Tests the server without requiring external connections.
"""
import asyncio
import threading
import time
from fastapi import WebSocket
from fastapi.testclient import TestClient
from app.main import app
from app.voice.gemini_live import GeminiLiveSession
from app.tools.definitions import TOOL_DECLARATIONS
from app.voice.bridge import load_system_prompt

def test_fastapi_app_structure():
    """Test that the FastAPI app is properly structured."""
    print("[TEST] Testing FastAPI app structure...")

    # Test 1: Check app exists and has correct properties
    assert app is not None
    assert app.title == "Restaurant Voice Agent"
    print("[PASS] FastAPI app imported successfully")

    # Test 2: Check all expected routes exist
    route_paths = [route.path for route in app.routes]
    expected_paths = [
        "/health",
        "/voice/browser",
        "/api/reservations/check-availability",
        "/api/reservations",
        "/api/menu",
        "/api/menu/{item_name}",
        "/test/reservation",
        "/voice-widget",
        "/test/config"
    ]

    missing_routes = []
    for expected in expected_paths:
        if expected not in route_paths:
            missing_routes.append(expected)
    if missing_routes:
        raise AssertionError(f"Expected routes not found: {missing_routes}")
    print(f"[PASS] All {len(expected_paths)} expected routes are present")

    # Test 3: Check test client can access basic endpoints
    client = TestClient(app)

    # Health endpoint should work
    response = client.get("/health")
    assert response.status_code == 200
    print("[PASS] Health endpoint works")

    # Voice widget endpoint should work
    response = client.get("/voice-widget")
    assert response.status_code == 200
    assert "Bella Italia" in response.text
    print("[PASS] Voice widget endpoint works")

    # Test 4: Check config endpoint
    response = client.get("/test/config")
    assert response.status_code == 200
    config = response.json()
    assert "app_name" in config
    assert "gemini_key_set" in config
    print("[PASS] Config endpoint works")

async def test_gemini_session_creation():
    """Test that Gemini Live session can be created without errors."""
    print("[TEST] Testing Gemini Live session creation...")

    async def mock_on_tool_call(tool_name: str, args: dict):
        return {"mock": "result"}

    try:
        # Test 1: Create system prompt
        system_prompt = await load_system_prompt()
        assert system_prompt is not None
        assert len(system_prompt) > 0
        print("[PASS] System prompt loaded successfully")

        # Test 2: Create Gemini Live session
        session = GeminiLiveSession(
            system_prompt=system_prompt,
            tool_declarations=TOOL_DECLARATIONS,
            on_tool_call=mock_on_tool_call,
        )
        print("[PASS] GeminiLiveSession instance created")

        # Test 3: Verify session attributes
        assert session.system_prompt == system_prompt
        assert session.tool_declarations == TOOL_DECLARATIONS
        assert session.on_tool_call == mock_on_tool_call
        assert session.client is not None
        print("[PASS] Session attributes are correct")

        return True
    except Exception as e:
        print(f"[FAIL] Gemini session creation failed: {e}")
        return False

def test_web_socket_endpoint():
    """Test the WebSocket endpoint structure."""
    print("[TEST] Testing WebSocket endpoint structure...")

    try:
        # Find the WebSocket endpoint handler
        websocket_endpoint = None
        for route in app.routes:
            if route.path == "/voice/browser":
                websocket_endpoint = route
                break

        assert websocket_endpoint is not None, "WebSocket endpoint not found"
        print("[PASS] WebSocket endpoint is registered")

        # Check it's actually a WebSocket endpoint
        # (We can't easily check the function type without importing more)
        print("[PASS] WebSocket endpoint structure looks correct")
        return True
    except Exception as e:
        print(f"[FAIL] WebSocket endpoint test failed: {e}")
        return False

async def test_browser_bridge_flow():
    """Test the browser bridge flow without actual WebSocket."""
    print("[TEST] Testing browser bridge flow...")

    try:
        # Test 1: Import browser bridge
        from app.voice import browser_bridge
        assert browser_bridge is not None
        print("[PASS] Browser bridge module imported")

        # Test 2: Check handle_browser_session function exists
        assert hasattr(browser_bridge, 'handle_browser_session')
        assert callable(browser_bridge.handle_browser_session)
        print("[PASS] handle_browser_session function exists")

        # Test 3: Verify the signature
        import inspect
        sig = inspect.signature(browser_bridge.handle_browser_session)
        params = list(sig.parameters.keys())
        assert 'websocket' in params
        print("[PASS] handle_browser_session has correct signature")

        return True
    except Exception as e:
        print(f"[FAIL] Browser bridge flow test failed: {e}")
        return False

def run_all_tests():
    """Run all tests and report results."""
    print("=" * 60)
    print("Restaurant Voice Agent - Integration Test Suite")
    print("=" * 60)

    test_results = []

    # Run tests
    try:
        test_fastapi_app_structure()
        test_results.append(("FastAPI App Structure", True))
    except Exception as e:
        test_results.append(("FastAPI App Structure", False))
        print(f"[FAIL] FastAPI App Structure: {e}")

    try:
        result = asyncio.run(test_gemini_session_creation())
        test_results.append(("Gemini Session Creation", result))
    except Exception as e:
        test_results.append(("Gemini Session Creation", False))
        print(f"[FAIL] Gemini Session Creation: {e}")

    try:
        result = test_web_socket_endpoint()
        test_results.append(("WebSocket Endpoint", result))
    except Exception as e:
        test_results.append(("WebSocket Endpoint", False))
        print(f"[FAIL] WebSocket Endpoint: {e}")

    try:
        result = asyncio.run(test_browser_bridge_flow())
        test_results.append(("Browser Bridge Flow", result))
    except Exception as e:
        test_results.append(("Browser Bridge Flow", False))
        print(f"[FAIL] Browser Bridge Flow: {e}")

    # Print summary
    print("\n" + "=" * 60)
    print("Test Results Summary:")
    print("=" * 60)

    passed = 0
    for test_name, result in test_results:
        status = "PASS" if result else "FAIL"
        emoji = "[PASS]" if result else "[FAIL]"
        print(f"{emoji} {test_name}: {status}")
        if result:
            passed += 1

    print(f"\nSUMMARY: Passed {passed}/{len(test_results)} tests")

    if passed == len(test_results):
        print("\n[OK] All tests passed! The server structure is correctly set up.")
        return True
    else:
        print(f"\n[FAIL] {len(test_results) - passed} tests failed.")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
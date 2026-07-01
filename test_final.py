"""
Final test to verify FastAPI server browser voice functionality.
Simple version without Unicode characters.
"""
from fastapi.testclient import TestClient
from app.main import app

def test_app_structure():
    """Test basic FastAPI app structure."""
    print("TEST: Checking FastAPI app structure...")

    # Check app exists
    assert app is not None
    print("PASS: FastAPI app imported")

    # Check routes
    route_paths = [route.path for route in app.routes]
    expected_routes = [
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

    for route in expected_routes:
        if route not in route_paths:
            print(f"FAIL: Expected route {route} not found")
            return False
    print(f"PASS: All {len(expected_routes)} routes present")
    return True

def test_basic_endpoints():
    """Test basic endpoints work."""
    print("TEST: Testing basic endpoints...")

    client = TestClient(app)

    # Health endpoint
    resp = client.get("/health")
    if resp.status_code != 200:
        print(f"FAIL: Health endpoint status {resp.status_code}")
        return False
    print("PASS: Health endpoint works")

    # Voice widget
    resp = client.get("/voice-widget")
    if resp.status_code != 200:
        print(f"FAIL: Voice widget endpoint status {resp.status_code}")
        return False
    if "Bella Italia" not in resp.text:
        print("FAIL: Voice widget HTML missing Bella Italia")
        return False
    print("PASS: Voice widget endpoint works")

    # Config
    resp = client.get("/test/config")
    if resp.status_code != 200:
        print(f"FAIL: Config endpoint status {resp.status_code}")
        return False
    config = resp.json()
    if "app_name" not in config:
        print("FAIL: Config missing app_name")
        return False
    print("PASS: Config endpoint works")

    return True

def main():
    print("=" * 60)
    print("Restaurant Voice Agent - Final Test Suite")
    print("=" * 60)

    tests = [
        ("App Structure", test_app_structure),
        ("Basic Endpoints", test_basic_endpoints),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"RESULT: {test_name} - PASS")
            else:
                print(f"RESULT: {test_name} - FAIL")
        except Exception as e:
            print(f"RESULT: {test_name} - ERROR: {e}")

    print("=" * 60)
    print(f"SUMMARY: {passed}/{total} tests passed")

    if passed == total:
        print("SUCCESS: All tests passed!")
        return True
    else:
        print(f"FAILURE: {total - passed} tests failed")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
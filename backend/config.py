"""
Central configuration. Everything here is loaded from environment variables
(see .env.example). Nothing is hardcoded so the same code runs for any
restaurant by just changing the .env file.
"""
import os
from dotenv import load_dotenv

load_dotenv()


def _get(name: str, default: str | None = None, required: bool = False) -> str:
    val = os.environ.get(name, default)
    if required and not val:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            f"Copy .env.example to .env and fill it in."
        )
    return val


# --- Gemini ---
GEMINI_API_KEY = _get("GEMINI_API_KEY", required=True)
# gemini-2.5-flash-native-audio-latest is the current stable Live API model.
# gemini-3.1-flash-live-preview is newer (90+ languages, stronger function
# calling) but preview-tier - swap in .env if you want to try it.
GEMINI_MODEL = _get("GEMINI_MODEL", "gemini-2.5-flash-native-audio-latest")
GEMINI_VOICE = _get("GEMINI_VOICE", "Puck")  # Puck, Charon, Kore, Fenrir, Aoede...

# --- Restaurant identity / behavior ---
RESTAURANT_NAME = _get("RESTAURANT_NAME", "The Golden Fork")
RESTAURANT_HOURS = _get("RESTAURANT_HOURS", "Mon-Sun, 11:00 AM - 10:00 PM")
RESTAURANT_ADDRESS = _get("RESTAURANT_ADDRESS", "123 Main Street")
RESTAURANT_PHONE = _get("RESTAURANT_PHONE", "+1-555-0100")

# --- Database ---
DATABASE_URL = _get("DATABASE_URL", "sqlite:///./restaurant.db")

# --- Twilio (optional - only needed for real inbound phone calls) ---
TWILIO_ACCOUNT_SID = _get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = _get("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = _get("TWILIO_PHONE_NUMBER", "")

# Public base URL of this server, e.g. https://your-ngrok-domain.ngrok-free.app
# Used to build the wss:// media stream URL Twilio connects back to, and for
# building callback links. No trailing slash.
PUBLIC_BASE_URL = _get("PUBLIC_BASE_URL", "").rstrip("/")

# --- Server ---
HOST = _get("HOST", "0.0.0.0")
PORT = int(_get("PORT", "8000"))

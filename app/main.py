"""
Restaurant Voice Agent — FastAPI Application

Browser-based voice agent for restaurants.
Opens a WebSocket for browser mic → Gemini Live API → spoken response.

Endpoints:
- /voice/browser          — WebSocket for browser mic audio (PCM16)
- /api/reservations/*     — REST API for reservations
- /api/menu/*             — REST API for menu browsing
- /test/reservation       — Simulate a reservation flow (no audio needed)
- /voice-widget           — Test HTML page with the voice widget
- /health                 — Health check
"""

from contextlib import asynccontextmanager
from datetime import date, time

from fastapi import Depends, FastAPI, HTTPException, Query, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import close_db, get_session, init_db
from app.schemas import (
    AvailabilityRequest,
    AvailabilityResponse,
    MenuItemResponse,
    ReservationCreate,
    ReservationResponse,
    TableResponse,
)
from app.services import menu as menu_service
from app.services import reservations as res_service

# ── Lifespan ────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB tables. Shutdown: dispose engine."""
    logger.info(f"Starting {settings.APP_NAME}...")
    await init_db()
    logger.info("Database tables initialized")
    yield
    await close_db()
    logger.info("Application shutting down")


# ── App ─────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware is intentionally omitted for local dev.
# The voice widget is served from the same origin.
# For production, add CORSMiddleware and exclude /voice/* paths
# from its scope to avoid blocking WebSocket upgrades.


# ── Health ──────────────────────────────────────────────────────


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME}


# ── Voice WebSocket (Browser mic → Gemini) ─────────────────────


@app.websocket("/voice/browser")
async def browser_voice(websocket: WebSocket):
    """
    WebSocket endpoint for browser-based voice.

    The browser sends PCM16 16kHz mono audio chunks (binary).
    The server relays them to Gemini Live API and streams the
    spoken response back as binary PCM16 audio.

    Protocol:
    1. Client opens WebSocket to /voice/browser
    2. Server starts a Gemini Live session with tools + system prompt
    3. Client streams raw PCM16 audio chunks (binary messages)
    4. Server receives Gemini audio + tool call responses
    5. Gemini audio is streamed back to client as binary messages
    6. Tool results (text) come as JSON messages: {"type": "tool_result", ...}
    7. Close the WebSocket to end the call
    """
    from app.voice.browser_bridge import handle_browser_session
    await handle_browser_session(websocket)


# ── API: Reservations ───────────────────────────────────────────


@app.post("/api/reservations/check-availability", response_model=AvailabilityResponse)
async def api_check_availability(
    req: AvailabilityRequest,
    session: AsyncSession = Depends(get_session),
):
    """Check table availability for a given date/time/party_size."""
    available, tables = await res_service.check_table_availability(
        session, req.date, req.time, req.party_size
    )
    return AvailabilityResponse(
        available=available,
        suggested_tables=[
            TableResponse(
                id=t.id,
                table_number=t.table_number,
                capacity=t.capacity,
                is_available=t.is_available,
                location=t.location,
            )
            for t in tables
        ],
    )


@app.post("/api/reservations", response_model=ReservationResponse)
async def api_create_reservation(
    data: ReservationCreate,
    session: AsyncSession = Depends(get_session),
):
    """Create a new reservation (auto-assigns a suitable table)."""
    _, tables = await res_service.check_table_availability(
        session, data.reservation_date, data.reservation_time, data.party_size
    )
    table = tables[0] if tables else None
    reservation = await res_service.create_reservation(session, data, table=table)
    return ReservationResponse.model_validate(reservation)


# ── API: Menu ───────────────────────────────────────────────────


@app.get("/api/menu", response_model=list[MenuItemResponse])
async def api_get_menu(
    category: str | None = Query(None, description="Filter by category"),
    session: AsyncSession = Depends(get_session),
):
    """Get all menu items, optionally filtered by category."""
    from app.models import MenuCategory
    cat = MenuCategory(category) if category else None
    items = await menu_service.get_menu_by_category(session, cat)
    return [MenuItemResponse.model_validate(item) for item in items]


@app.get("/api/menu/{item_name}", response_model=MenuItemResponse)
async def api_get_menu_item(
    item_name: str,
    session: AsyncSession = Depends(get_session),
):
    """Look up a specific menu item by name (partial match)."""
    item = await menu_service.get_menu_item(session, name=item_name)
    if not item:
        raise HTTPException(status_code=404, detail=f"Menu item '{item_name}' not found")
    return MenuItemResponse.model_validate(item)


# ── Test: Simulated reservation flow ────────────────────────────


class TestReservationPayload(BaseModel):
    customer_name: str = "Test User"
    phone: str = "+15551112222"
    party_size: int = 4
    date: str = "2026-07-04"
    time: str = "19:00"


@app.post("/test/reservation")
async def test_reservation(
    body: TestReservationPayload,
    session: AsyncSession = Depends(get_session),
):
    """Simulate a complete reservation flow without a phone call."""
    res_date = date.fromisoformat(body.date)
    res_time = time.fromisoformat(body.time)

    available, tables = await res_service.check_table_availability(
        session, res_date, res_time, body.party_size
    )
    if not available:
        return {"success": False, "step": "check_availability", "message": "No tables available at that time."}

    data = ReservationCreate(
        customer_name=body.customer_name,
        phone=body.phone,
        party_size=body.party_size,
        reservation_date=res_date,
        reservation_time=res_time,
    )
    reservation = await res_service.create_reservation(session, data, table=tables[0])

    return {
        "success": True,
        "reservation_id": reservation.id,
        "customer": reservation.customer_name,
        "date": str(reservation.reservation_date),
        "time": str(reservation.reservation_time),
        "party_size": reservation.party_size,
        "table": tables[0].table_number if tables else None,
        "message": (
            f"Reservation confirmed for {reservation.customer_name} — "
            f"{reservation.party_size} guests at {reservation.reservation_time} "
            f"on {reservation.reservation_date}"
        ),
    }


# ── Test: Voice widget HTML page ────────────────────────────────


VOICE_WIDGET_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Bella Italia - Voice Assistant</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
  }
  .container {
    text-align: center;
    padding: 2rem;
    max-width: 500px;
  }
  h1 { font-size: 2rem; margin-bottom: 0.5rem; }
  .subtitle { color: #a0aec0; margin-bottom: 2rem; }
  .mic-button {
    width: 120px; height: 120px;
    border-radius: 50%;
    border: 3px solid #4299e1;
    background: rgba(66, 153, 225, 0.1);
    cursor: pointer;
    transition: all 0.3s;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto 2rem;
  }
  .mic-button:hover { background: rgba(66, 153, 225, 0.2); }
  .mic-button.listening { border-color: #fc8181; background: rgba(252, 129, 129, 0.2); animation: pulse 1.5s infinite; }
  .mic-button.thinking { border-color: #ecc94b; background: rgba(236, 201, 75, 0.2); }
  @keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(252, 129, 129, 0.4); } 70% { box-shadow: 0 0 0 30px rgba(252, 129, 129, 0); } 100% { box-shadow: 0 0 0 0 rgba(252, 129, 129, 0); } }
  .mic-icon { font-size: 3rem; }
  .status { color: #a0aec0; margin-bottom: 1rem; min-height: 1.5rem; font-size: 0.9rem; }
  .transcript { background: rgba(255,255,255,0.05); border-radius: 12px; padding: 1rem; min-height: 60px; margin-bottom: 1rem; font-size: 0.95rem; color: #e2e8f0; text-align: left; max-height: 200px; overflow-y: auto; }
  .transcript .label { color: #718096; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem; }
  .transcript .you { color: #90cdf4; }
  .transcript .ai { color: #fbbf24; }
  .error { color: #fc8181; font-size: 0.85rem; margin-top: 1rem; display: none; }
  .error.visible { display: block; }
</style>
</head>
<body>
<div class="container">
  <h1>🍝 Bella Italia</h1>
  <p class="subtitle">Voice Assistant</p>

  <div id="micButton" class="mic-button">
    <span class="mic-icon">🎤</span>
  </div>

  <div class="status" id="status">Press the mic to start speaking</div>

  <div class="transcript" id="transcript">
    <div class="label">Conversation</div>
    <div id="conversation"><em style="color:#718096">Start speaking to see the conversation here...</em></div>
  </div>

  <div class="error" id="error"></div>
</div>

<script>
// ── Configuration ─────────────────────────────────────────────
const WS_URL = `ws://${location.host}/voice/browser`;
const SAMPLE_RATE = 16000;

// ── State ─────────────────────────────────────────────────────
let ws = null;
let audioContext = null;
let processor = null;
let micStream = null;
let isConnected = false;
let isListening = false;

const micButton = document.getElementById('micButton');
const statusEl = document.getElementById('status');
const transcriptEl = document.getElementById('conversation');
const errorEl = document.getElementById('error');

// ── Helpers ───────────────────────────────────────────────────

function addTranscript(role, text) {
  const emoji = role === 'you' ? '🧑' : '🤖';
  const cls = role === 'you' ? 'you' : 'ai';
  const line = document.createElement('div');
  line.innerHTML = `<span class="${cls}">${emoji} <strong>${role === 'you' ? 'You' : 'Bella'}:</strong> ${text}</span>`;
  transcriptEl.appendChild(line);
  transcriptEl.parentElement.scrollTop = transcriptEl.parentElement.scrollHeight;
}

function showError(msg) {
  errorEl.textContent = msg;
  errorEl.classList.add('visible');
}

function hideError() {
  errorEl.classList.remove('visible');
}

function setStatus(text, isError) {
  statusEl.textContent = text;
  statusEl.style.color = isError ? '#fc8181' : '#a0aec0';
}

// ── PCM16 capture via AudioContext ScriptProcessor ────────────

function float32ToInt16(float32) {
  const int16 = new Int16Array(float32.length);
  for (let i = 0; i < float32.length; i++) {
    const s = Math.max(-1, Math.min(1, float32[i]));
    int16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
  }
  return int16;
}

async function startListening() {
  hideError();
  setStatus('Requesting microphone...');

  // Get mic
  try {
    micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (e) {
    showError('Microphone access denied. Please allow mic access and try again.');
    return;
  }

  // Connect WebSocket
  ws = new WebSocket(WS_URL);
  ws.binaryType = 'arraybuffer';

  ws.onopen = async () => {
    isConnected = true;
    isListening = true;
    setStatus('Listening...');
    micButton.classList.add('listening');

    // Set up AudioContext (16kHz to match Gemini)
    audioContext = new AudioContext({ sampleRate: SAMPLE_RATE });
    const source = audioContext.createMediaStreamSource(micStream);

    // ScriptProcessorNode for raw PCM access
    // bufferSize=4096 gives ~256ms chunks at 16kHz — good balance
    processor = audioContext.createScriptProcessor(4096, 1, 1);
    processor.onaudioprocess = (event) => {
      if (!ws || ws.readyState !== WebSocket.OPEN) return;

      const input = event.inputBuffer.getChannelData(0); // Float32 samples
      const pcm16 = float32ToInt16(input);               // Convert to PCM16
      ws.send(pcm16.buffer);                             // Send raw bytes
      addTranscript('you', '(speaking...)');
    };

    source.connect(processor);
    processor.connect(audioContext.destination);
  };

  ws.onmessage = async (event) => {
    if (event.data instanceof ArrayBuffer) {
      // PCM16 audio from Gemini — play it
      const pcm16 = new Int16Array(event.data);

      // Convert to Float32 for AudioBuffer
      const float32 = new Float32Array(pcm16.length);
      for (let i = 0; i < pcm16.length; i++) {
        float32[i] = pcm16[i] / (pcm16[i] < 0 ? 0x8000 : 0x7FFF);
      }

      const audioBuffer = audioContext.createBuffer(1, float32.length, SAMPLE_RATE);
      audioBuffer.getChannelData(0).set(float32);

      const source = audioContext.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(audioContext.destination);
      source.start();
    } else {
      // JSON message
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'connected') {
          setStatus('Connected! Start speaking.');
        } else if (msg.type === 'text') {
          addTranscript('ai', msg.text);
        }
      } catch (e) {
        addTranscript('ai', event.data);
      }
    }
  };

  ws.onerror = () => {
    showError('Connection error. Make sure the server is running.');
    stopListening();
  };

  ws.onclose = () => {
    setStatus('Disconnected');
    micButton.classList.remove('listening');
    isConnected = false;
    isListening = false;
  };
}

function stopListening() {
  if (processor) { processor.disconnect(); processor = null; }
  if (audioContext) { audioContext.close(); audioContext = null; }
  if (micStream) { micStream.getTracks().forEach(t => t.stop()); micStream = null; }
  if (ws) { ws.close(); ws = null; }
  isConnected = false;
  isListening = false;
  setStatus('Press the mic to start');
  micButton.classList.remove('listening');
}

micButton.addEventListener('click', () => {
  isListening ? stopListening() : startListening();
});
</script>
</body>
</html>
"""


@app.get("/voice-widget", response_class=HTMLResponse)
async def voice_widget_page():
    """Serve the test voice widget HTML page."""
    return HTMLResponse(VOICE_WIDGET_HTML)


# ── Config check ────────────────────────────────────────────────


@app.get("/test/config")
async def test_config():
    """Verify configuration is loaded correctly (sensitive fields masked)."""
    db_masked = settings.DATABASE_URL
    if "@" in db_masked:
        auth, rest = db_masked.split("@")
        scheme_and_creds = auth.split("://")
        db_masked = f"{scheme_and_creds[0]}://****:****@{rest}"

    return {
        "app_name": settings.APP_NAME,
        "database_url": db_masked,
        "gemini_key_set": bool(settings.GEMINI_API_KEY),
        "square_configured": bool(settings.SQUARE_ACCESS_TOKEN and settings.SQUARE_LOCATION_ID),
    }

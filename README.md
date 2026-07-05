# Restaurant Voice Agent

A browser-based voice agent for restaurants powered by **Gemini Live API**. Customers can talk naturally to place orders, make reservations, and ask menu questions — all through a retro-terminal web interface.

## Features

- **🎙️ Voice Conversations** — Real-time audio streaming via WebSocket + Gemini Live API
- **📋 Menu Q&A** — Answers questions about menu items, prices, and ingredients
- **🍽️ Order Taking** — Takes food orders conversationally, reads them back for confirmation
- **📅 Reservations** — Checks table availability and books reservations
- **🖥️ Online Ordering** — Click-to-order page for customers who prefer typing
- **📊 Analytics Dashboard** — Daily trends, top items, peak hours, revenue KPIs
- **👨‍🍳 Admin Order Management** — Kitchen lane view with status controls
- **🔍 Order Lookup** — Search orders by phone number or order ID

## Quick Start

### Prerequisites
- Python 3.14+ (3.12+ should also work)
- A Gemini API key from [aistudio.google.com](https://aistudio.google.com/apikey)

### Setup

```bash
# Clone (or copy) and enter the project directory
cd restaurant-voice-agent

# Create a virtual environment
python -m venv venv
venv\Scripts\activate   # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Configure your environment
cp .env.example .env
# Edit .env — set your GEMINI_API_KEY and restaurant info
```

### Run

```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000** in a browser (Chrome/Firefox recommended). Click **PICK UP** to start a voice conversation.

### Pages

| Page | URL | Description |
|------|-----|-------------|
| Voice Terminal | `/` | Main voice interface |
| Admin Dashboard | `/admin` | Kitchen order lanes |
| Order Lookup | `/order-lookup` | Search orders |
| Analytics | `/analytics` | Business metrics |
| Online Ordering | `/order` | Customer order form |

## Architecture

```
backend/
├── main.py            # FastAPI app, WebSocket endpoint, static serving
├── gemini_session.py  # Gemini Live API session wrapper
├── web_routes.py      # REST API endpoints & page routes
├── twilio_routes.py   # Twilio phone integration (optional)
├── db.py              # SQLAlchemy models (Menu, Order, Reservation, etc.)
├── tools.py           # Tool declarations & executor for Gemini
├── config.py          # Environment config
├── audio_utils.py     # Audio format conversion helpers
├── seed_data.py       # Seed menu items & tables

frontend/
├── index.html         # Main voice terminal
├── admin.html         # Kitchen order dashboard
├── order-lookup.html  # Order search
├── analytics.html     # Analytics dashboard
└── order.html         # Online ordering page
```

### Audio Specs

- **Capture**: 48 kHz → downsampled to 16 kHz PCM16 mono
- **Playback**: 24 kHz PCM16 mono (Gemini output format)
- **Transport**: WebSocket binary frames

### Tech Stack

- **Backend**: Python FastAPI + SQLAlchemy + SQLite
- **Voice AI**: Gemini 2.5 Flash (Live Audio API)
- **Frontend**: Vanilla JavaScript + Web Audio API + CSS retro terminal theme

## License

MIT

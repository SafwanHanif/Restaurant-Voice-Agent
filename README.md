# Restaurant Voice Agent

A browser-based voice agent for restaurants using Gemini Live API.

## Overview

Restaurant Voice Agent is a complete voice-enabled restaurant system that allows customers to interact with a restaurant's menu, check availability, make reservations, and get food recommendations using natural voice commands.

## Core Architecture

The system is divided into two main components:

### Backend (Python FastAPI)
- **Web Framework**: FastAPI with WebSocket support
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Voice Integration**: Gemini Live API session management
- **API Endpoints**:
  - `/voice/browser` - WebSocket for browser voice commands
  - `/api/reservations/*` - Reservation management API
  - `/api/menu/*` - Menu browsing API
  - `/test/reservation` - Test reservation endpoint
  - `/voice-widget` - Voice interface HTML page
  - `/health` - Health check endpoint

### Frontend (Browser)
- **Voice Widget**: Web-based interface with microphone button
- **WebSocket Connection**: Real-time audio streaming
- **Audio Processing**: PCM16 16kHz audio capture and playback
- **Speech-to-Text**: Gemini Live speech recognition
- **Text-to-Speech**: Gemini Live voice generation

## Quick Start

### Prerequisites
- Python 3.9+
- PostgreSQL database
- Gemini API key

### Installation
```bash
# Clone the repository
git clone https://github.com/SafwanHanif/Restaurant-Voice-Agent.git
\ncd Restaurant-Voice-Agent

# Install dependencies
pip install -r requirements.txt

# Create .env file from .env.example
 cp .env.example .env

# Update .env with your API keys and database credentials

# Initialize database
python -m app.seed
```

### Running the Server
```bash
python -m app.main
```

The server will run on `http://localhost:8000`

### Testing
```bash
# Run integration tests
python test_basic.py

# Test individual components
python final_integration_test.py
```

## Features

### Voice Assistant Capabilities
- **Reservation Management**: Check availability, make reservations, cancel bookings
- **Menu Browsing**: Browse categories, view items, get ingredient/allergen information
- **Customer Preferences**: Handle dietary restrictions, special requests
- **Escalation**: Transfer to human manager when needed

### Technical Features
- **Real-time Audio Processing**: PCM16 16kHz audio streaming via WebSocket
- **Bidirectional Communication**: Browser ↔ Gemini Live API integration
- **Error Handling**: Robust error handling and recovery
- **Session Management**: Per-call Gemini Live session management
- **Tool Integration**: Seamless database integration for all operations

## API Endpoints

### Voice Interaction
```
GET /health                    # Health check
GET /voice-widget              # Voice widget HTML page
POST /test/reservation          # Test reservation simulation
```

### Menu Operations
```
GET /api/menu                  # Get all menu items
GET /api/menu/{item_name}      # Get specific menu item
```

### Reservation Operations
```
POST /api/reservations/check-availability  # Check table availability
POST /api/reservations                    # Create reservation
```

## Development

### Project Structure
```
Restaurant-Voice-Agent/
├── app/
│   ├── __init__.py              # Application package
│   ├── config.py                # Configuration settings
│   ├── database.py             # Database connection and models
│   ├── main.py                 # FastAPI application entry point
│   ├── models.py               # SQLAlchemy ORM models
│   ├── schemas.py              # Pydantic request/response schemas
│   ├── seed.py                 # Database seeding script
│   ├── services/              # Application services
│   │   ├── __init__.py
│   │   ├── menu.py             # Menu service
│   │   ├── reservations.py     # Reservation service
│   │   └── ordering.py         # Ordering service
│   ├── tools/                 # Gemini function definitions and handlers
│   │   ├── __init__.py
│   │   └── definitions.py      # Tool declarations and dispatcher
│   ├── voice/                 # Voice bridge components
│   │   ├── __init__.py
│   │   ├── audio.py            # Audio processing utilities
│   │   ├── bridge.py           # System prompt loading
│   │   ├── browser_bridge.py   # Browser WebSocket connection handler
│   │   ├── gemini_live.py     # Gemini Live session management
│   │   └── livekit_bridge.py  # LiveKit browser voice support
│   └── webhooks/              # Webhook handlers
│       ├── __init__.py
│       ├── twilio_webhooks.py  # Twilio webhook handlers
│       └── sms.py             # SMS notification service
├── alembic/                    # Database migrations
│   ├── __init__.py
│   └── versions/              # Migration scripts
├── prompts/                   # System prompt templates
│   └── system_prompt.txt     # AI receptionist prompt
├── docker-compose.yml         # Docker configuration
├── requirements.txt           # Python dependencies
├── .env.example              # Environment variables template
├── .gitignore               # Git ignore file
└── README.md                # This file
```

### Workflow
1. **User Interaction**: Customer speaks to the voice interface in their browser
2. **Speech Processing**: Audio captured via browser microphone, sent to Gemini Live
3. **Intent Recognition**: Gemini processes speech, identifies user intent
4. **Tool Calling**: Appropriate restaurant functions called (availability checks, menu lookups, etc.)
5. **Response Generation**: Gemini generates spoken responses
6. **Database Integration**: All operations persist to PostgreSQL database
7. **Feedback Loop**: Audio responses played back to customer via browser

## WebSocket Protocol

### Client-Side (Browser)
1. Browser connects to `ws://localhost:8000/voice/browser`
2. Browser sends PCM16 16kHz audio bytes for speech
3. Browser receives:
   - PCM16 audio bytes for voice responses
   - JSON text messages for transcripts and tool results

### Server-Side (Python)
1. Server accepts WebSocket connection at `/voice/browser`
2. Server immediately sends `{"type": "connected", "message": "..."}` (server-initiated)
3. Server processes incoming audio and forwards to Gemini Live API
4. Server receives Gemini responses and forwards to browser
5. Connection continues until either side disconnects

## Testing

The system includes comprehensive tests:

### Unit Tests
```bash
python test_basic.py
python final_integration_test.py
python integration_runner.py
```

### Test Coverage
- ✅ Backend API endpoints
- ✅ Voice widget HTML structure
- ✅ Configuration loading
- ✅ Menu browsing functionality
- ✅ Reservation system
- ✅ Gemini Live session integration

## Future Enhancements

### Phase 2
- Square POS integration for order management
- Payment processing via Stripe
- Advanced NLP for better intent recognition
- Multi-language support

### Phase 3
- Dashboard for restaurant staff
- Call analytics and reporting
- Integration with existing restaurant systems
- Mobile app support

## Contributing

1. Fork this repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contact

For issues, questions, or contributions:
- GitHub Issues: [Repository Issues]
- Email: [Your Email]

---

**Built with**
- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework
- [Gemini Live API](https://developers.generativeai.google/live) - Voice AI
- [PostgreSQL](https://www.postgresql.org/) - Database
- [Python](https://www.python.org/) - Application language
- [WebSockets](https://tools.ietf.org/html/rfc6455) - Real-time communication

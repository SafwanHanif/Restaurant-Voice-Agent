# Restaurant Voice Agent

A browser-based voice agent for restaurants using Gemini Live API.

## Quick Start

This project implements a real-time voice assistant for restaurants that can:
- Answer menu questions
- Check table availability
- Take reservations  
- Provide restaurant information

### Running the Server

```bash
# Start the FastAPI server
python -m app.main

# Test with curl
curl http://localhost:8000/health
```

### Browser Access

Open your browser to:
```
http://localhost:8000/voice-widget
```

This will load the voice interface with the microphone button.

### Testing

```bash
# Run integration tests
python test_basic.py

# Or run the full test suite
python final_integration_test.py
```

## Architecture

### Backend: Python FastAPI
- **WebSocket**: `/voice/browser` for real-time audio streaming
- **REST API**: `/api/reservations/*`, `/api/menu/*` for operations
- **Database**: PostgreSQL via SQLAlchemy ORM
- **Voice AI**: Gemini Live API integration

### Frontend: Browser JavaScript
- **Audio Processing**: PCM16 16kHz capture and playback
- **WebSocket**: Real-time bidirectional messaging
- **UI**: Voice widget with microphone interface
- **Speech I/O**: Automatic speech recognition and synthesis

## Key Features

1. **Voice Commands**: Natural language reservation and menu queries
2. **Real-time Audio**: Bidirectional audio streaming (16kHz PCM16)
3. **Tool Integration**: Seamless database and API calls
4. **Error Handling**: Robust error recovery and user feedback
5. **Session Management**: Per-call voice interaction tracking

## Files Updated

### Protocol Fix
- **`app/voice/browser_bridge.py`**: Fixed WebSocket protocol to send `{"type": "connected", "message": "..."}` immediately after connection
- **`app/main.py`**: WebSocket endpoint `/voice/browser` maintained

### Other Improvements
- **`.gitignore`**: Enhanced to exclude sensitive files
- **`README.md`**: Added comprehensive documentation

## WebSocket Protocol

### Client-Side Flow
1. Browser connects to `ws://localhost:8000/voice/browser`
2. Browser expects server to send `{"type": "connected", "message": "..."}`
3. Server sends confirmation immediately after accepting connection
4. Browser then sends audio bytes and receives responses

### Server-Side Flow
1. Server accepts WebSocket connection
2. **IMMEDIATELY** sends `{"type": "connected", "message": "Connected to Bella Italia voice assistant. Start speaking!"`
3. Server processes audio from browser and forwards to Gemini Live API
4. Server receives Gemini responses and forwards to browser
5. Loop continues until disconnect

## Technical Details

### Audio Specifications
- **Format**: PCM16 (16-bit signed integers)
- **Sample Rate**: 16,000 Hz
- **Channels**: Mono (single channel)
- **Codec**: Raw audio streaming

### API Endpoints
```
GET /health                    # Health check
GET /voice-widget              # Voice widget HTML
POST /test/reservation          # Test reservation (no audio)
```

### Backend APIs
```
POST /api/reservations/check-availability
POST /api/reservations
GET /api/menu
GET /api/menu/{item_name}
```

## Development

### Dependencies
```bash
pip install -r requirements.txt
```

### Database Setup
```bash
# Initialize database
python -m app.seed
```

### Testing
```bash
# Core functionality test
python test_basic.py

# Full integration test
python final_integration_test.py

# Protocol analysis
python integration_runner.py
```

## Future Enhancements

### Phase 2
- Square POS integration
- Payment processing
- Advanced NLP for better intent recognition
- Multi-language support

### Phase 3
- Staff dashboard
- Call analytics
- Mobile app support
- Advanced restaurant management

## Contributing

1. Fork the repository
2. Create a feature branch
3. Implement changes
4. Test thoroughly
5. Submit a pull request

## License

MIT License

## Contact

For issues or contributions:
- GitHub Issues
- [openhands](mailto:openhands@all-hands.dev)

---

**Project Type**: Voice AI Assistant
**Technology Stack**: FastAPI, Gemini Live, PostgreSQL, WebSocket, Audio Processing
**Target Platform**: Web browsers with microphone access
**Core Functionality**: Voice-based restaurant reservations and menu queries
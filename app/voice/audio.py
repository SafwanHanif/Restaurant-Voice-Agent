"""
Audio utilities for the voice bridge.

Twilio sends µ-law encoded 8kHz audio.
Gemini Live API expects PCM16 16kHz audio.
This module handles the conversion between them.
"""

import audioop
import struct
from typing import AsyncIterator

# Twilio → Gemini: µ-law 8kHz → PCM16 16kHz
TWILIO_SAMPLE_RATE = 8000
GEMINI_SAMPLE_RATE = 16000


def mulaw_to_pcm16(mulaw_bytes: bytes) -> bytes:
    """Convert µ-law 8kHz audio to PCM16 16kHz (upsample 2×)."""
    # Step 1: µ-law → PCM16 at 8kHz
    pcm8k = audioop.ulaw2lin(mulaw_bytes, 2)  # 2 bytes per sample = 16-bit
    # Step 2: Upsample 8kHz → 16kHz (double sample rate by linear interpolation)
    pcm16k = audioop.ratecv(pcm8k, 2, 1, TWILIO_SAMPLE_RATE, GEMINI_SAMPLE_RATE, None)[0]
    return pcm16k


def pcm16_to_mulaw(pcm16_bytes: bytes) -> bytes:
    """Convert PCM16 16kHz audio back to µ-law 8kHz for Twilio."""
    # Step 1: Downsample 16kHz → 8kHz
    pcm8k = audioop.ratecv(pcm16_bytes, 2, 1, GEMINI_SAMPLE_RATE, TWILIO_SAMPLE_RATE, None)[0]
    # Step 2: PCM16 → µ-law
    mulaw = audioop.lin2ulaw(pcm8k, 2)
    return mulaw


def chunk_audio(data: bytes, chunk_size_ms: int = 20) -> list[bytes]:
    """Split audio bytes into fixed-size chunks (e.g., 20ms for streaming)."""
    frame_size = int(GEMINI_SAMPLE_RATE * 2 * (chunk_size_ms / 1000))  # 16bit * channels=1
    return [data[i : i + frame_size] for i in range(0, len(data), frame_size)]


def silence(duration_ms: int = 100) -> bytes:
    """Generate silence (PCM16 16kHz) of given duration in ms."""
    samples = int(GEMINI_SAMPLE_RATE * (duration_ms / 1000))
    return struct.pack(f"<{samples}h", *([0] * samples))

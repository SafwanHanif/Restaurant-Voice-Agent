"""
Audio format conversion between Twilio (8kHz mulaw), the browser widget
(variable rate PCM16), and Gemini Live (16kHz PCM16 in, 24kHz PCM16 out).

Uses numpy + scipy instead of the stdlib `audioop` module on purpose:
audioop is deprecated and slated for removal, so this stays correct on
whatever Python version this ends up deployed on.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import resample_poly

# ---- mu-law (G.711) <-> linear PCM16 -------------------------------------

_MULAW_BIAS = 0x84
_MULAW_CLIP = 32635


def mulaw_to_pcm16(mulaw_bytes: bytes) -> bytes:
    """Decode 8-bit mu-law bytes to 16-bit signed linear PCM bytes."""
    data = np.frombuffer(mulaw_bytes, dtype=np.uint8).astype(np.int32)
    data = ~data & 0xFF
    sign = data & 0x80
    exponent = (data >> 4) & 0x07
    mantissa = data & 0x0F
    magnitude = ((mantissa << 3) + _MULAW_BIAS) << exponent
    magnitude -= _MULAW_BIAS
    samples = np.where(sign != 0, -magnitude, magnitude).astype(np.int16)
    return samples.tobytes()


_SEG_END = np.array([0xFF, 0x1FF, 0x3FF, 0x7FF, 0xFFF, 0x1FFF, 0x3FFF, 0x7FFF], dtype=np.int32)


def pcm16_to_mulaw(pcm_bytes: bytes) -> bytes:
    """Encode 16-bit signed linear PCM bytes to 8-bit mu-law bytes (standard G.711)."""
    samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.int32)
    sign = np.where(samples < 0, 0x80, 0x00).astype(np.int32)
    magnitude = np.clip(np.abs(samples), 0, _MULAW_CLIP) + _MULAW_BIAS

    # exponent = index of first segment boundary >= magnitude
    exponent = np.searchsorted(_SEG_END, magnitude, side="left").astype(np.int32)
    exponent = np.clip(exponent, 0, 7)

    mantissa = (magnitude >> (exponent + 3)) & 0x0F
    mulaw_byte = ~(sign | (exponent << 4) | mantissa) & 0xFF
    return mulaw_byte.astype(np.uint8).tobytes()


# ---- sample rate conversion ------------------------------------------------


def resample_pcm16(pcm_bytes: bytes, from_rate: int, to_rate: int) -> bytes:
    """Resample 16-bit mono PCM audio between sample rates."""
    if from_rate == to_rate or not pcm_bytes:
        return pcm_bytes
    samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)
    # resample_poly wants an integer up/down ratio - use gcd reduction.
    g = np.gcd(from_rate, to_rate)
    up, down = to_rate // g, from_rate // g
    resampled = resample_poly(samples, up, down)
    resampled = np.clip(resampled, -32768, 32767).astype(np.int16)
    return resampled.tobytes()

"""
Shared utilities for voice bridges.

This module contains the `load_system_prompt` function used by
both browser_bridge.py and livekit_bridge.py.

The Twilio Media Stream bridge was removed — this project uses
browser-based voice (WebSocket or LiveKit) instead of phone calls.
"""

from datetime import date


async def load_system_prompt() -> str:
    """Read the system prompt template and inject dynamic variables.

    The template uses {current_date} and {current_day} placeholders
    so the AI receptionist knows today's date.
    """
    today = date.today()
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    day_name = days[today.weekday()]

    with open("prompts/system_prompt.txt", "r") as f:
        prompt = f.read()

    return prompt.format(
        current_date=today.isoformat(),
        current_day=day_name,
    )

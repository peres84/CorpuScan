from __future__ import annotations

import os

RESET = "\033[0m"
BOLD = "\033[1m"

_COLORS = {
    "ingest": "\033[38;5;45m",
    "finance": "\033[38;5;214m",
    "scripter": "\033[38;5;141m",
    "tts": "\033[38;5;118m",
    "hera": "\033[38;5;197m",
    "compose": "\033[38;5;51m",
    "tavily": "\033[38;5;33m",
    "gemini": "\033[38;5;220m",
    "elevenlabs": "\033[38;5;112m",
    "request": "\033[38;5;39m",
    "job": "\033[38;5;250m",
}


def stage_tag(name: str) -> str:
    if os.getenv("NO_COLOR"):
        return f"[{name.upper()}]"
    color = _COLORS.get(name.lower(), "\033[38;5;250m")
    return f"{BOLD}{color}[{name.upper()}]{RESET}"

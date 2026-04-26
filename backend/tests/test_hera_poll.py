from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.agents.hera import background_alt_hex, background_strong_hex
from app.schemas import BrandingPalette
from app.integrations.hera import HeraClient


def test_hera_poll_prefers_successful_output_over_lagging_top_level_status() -> None:
    client = HeraClient(api_key="test", base_url="https://api.hera.video/v1")

    normalized = client._normalize_poll_response(
        {
            "status": "in-progress",
            "outputs": [
                {
                    "status": "success",
                    "file_url": "https://cdn.hera.video/example.mp4",
                    "error": None,
                }
            ],
        }
    )

    assert normalized["top_level_status"] == "in-progress"
    assert normalized["status"] == "success"
    assert normalized["file_url"] == "https://cdn.hera.video/example.mp4"
    assert normalized["error"] is None


def test_background_variants_are_distinct_from_base_background() -> None:
    branding = BrandingPalette(
        background="#F9FAFB",
        text="#111827",
        secondary="#374151",
        accent="#06B6D4",
    )

    alt_hex = background_alt_hex(branding)
    strong_hex = background_strong_hex(branding)

    assert alt_hex != branding.background
    assert strong_hex != branding.background
    assert alt_hex != strong_hex

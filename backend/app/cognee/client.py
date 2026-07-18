from __future__ import annotations

import logging
import os
from pathlib import Path

from app.config import get_settings

logger = logging.getLogger(__name__)


class CogneeClient:
    """Wrapper around the Cognee SDK providing init, reset, and availability checks.

    Handles graceful degradation: if Cognee is disabled or the SDK fails to
    initialize, all methods return safe defaults and the investigation
    continues without Cognee.
    """

    def __init__(self) -> None:
        self._initialized = False
        self._available = False

    async def init(self) -> bool:
        """Initialize Cognee. Returns True if successful, False otherwise."""
        settings = get_settings()

        if not settings.cognee_enabled:
            logger.info("Cognee is disabled (COGNEE_ENABLED=false)")
            self._available = False
            return False

        try:
            import cognee  # noqa: F401 — verifies SDK is installed

            # Configure Cognee storage path
            storage_path = Path(settings.cognee_storage_path)
            storage_path.mkdir(parents=True, exist_ok=True)
            os.environ.setdefault("COGNEE_DATA_DIRECTORY", str(storage_path))

            # Configure the LLM model Cognee should use
            if settings.openai_key:
                os.environ.setdefault("OPENAI_API_KEY", settings.openai_key)

            self._initialized = True
            self._available = True
            logger.info("Cognee initialized (storage=%s, model=%s)", storage_path, settings.cognee_model)
            return True

        except ImportError:
            logger.warning("Cognee SDK not installed — continuing without knowledge memory")
            self._available = False
            return False
        except Exception:
            logger.exception("Cognee initialization failed — continuing without knowledge memory")
            self._available = False
            return False

    async def reset(self) -> None:
        """Reset Cognee memory. Safe to call even when Cognee is unavailable."""
        if not self._available:
            return

        try:
            import cognee
            await cognee.forget(everything=True)
            logger.info("Cognee memory reset")
        except Exception:
            logger.warning("Cognee reset failed — continuing")

    def is_available(self) -> bool:
        """Check if Cognee is initialized and available for use."""
        return self._available

    @property
    def initialized(self) -> bool:
        return self._initialized

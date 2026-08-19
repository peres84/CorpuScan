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

        if not settings.openai_api_key or settings.openai_api_key.strip().lower() in (
            "",
            "key_here",
            "your_api_key",
            "api_key_here",
            "replace_me",
        ):
            logger.warning(
                "Cognee enabled but no OPENAI_API_KEY set — disabling Cognee"
            )
            self._available = False
            return False

        try:
            import cognee

            # Configure Cognee storage path
            storage_path = Path(settings.cognee_storage_path)
            storage_path.mkdir(parents=True, exist_ok=True)

            # Set env vars as belt-and-suspenders
            os.environ["OPENAI_API_KEY"] = settings.openai_api_key
            os.environ["LLM_API_KEY"] = settings.openai_api_key
            os.environ["COGNEE_DATA_DIRECTORY"] = str(storage_path)

            # Use Cognee's config API directly
            cognee.config.set_llm_api_key(settings.openai_api_key)
            cognee.config.set_llm_provider("openai")
            cognee.config.set_llm_model(settings.cognee_model)

            self._initialized = True
            self._available = True
            logger.info(
                "Cognee initialized (storage=%s, model=%s)",
                storage_path,
                settings.cognee_model,
            )
            return True

        except ImportError:
            logger.warning(
                "Cognee SDK not installed — continuing without knowledge memory"
            )
            self._available = False
            return False
        except Exception:
            logger.exception(
                "Cognee initialization failed — continuing without knowledge memory"
            )
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

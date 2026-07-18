from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pytest

from app.cognee.client import CogneeClient


class TestCogneeClientInit:
    @pytest.mark.asyncio
    async def test_disabled_returns_false(self) -> None:
        """When COGNEE_ENABLED=false, init returns False and client is unavailable."""
        with patch("app.cognee.client.get_settings") as mock_settings:
            mock_settings.return_value.cognee_enabled = False
            mock_settings.return_value.cognee_storage_path = "/tmp/cognee_test"
            mock_settings.return_value.cognee_model = "gpt-4o"
            mock_settings.return_value.openai_key = ""

            client = CogneeClient()
            result = await client.init()

            assert result is False
            assert client.is_available() is False
            assert client.initialized is False

    @pytest.mark.asyncio
    async def test_missing_sdk_degrades_gracefully(self) -> None:
        """When cognee package is not importable, init returns False gracefully."""
        with patch("app.cognee.client.get_settings") as mock_settings:
            mock_settings.return_value.cognee_enabled = True
            mock_settings.return_value.cognee_storage_path = "/tmp/cognee_test"
            mock_settings.return_value.cognee_model = "gpt-4o"
            mock_settings.return_value.openai_key = "test-key"

            # Simulate cognee not being installed
            import builtins
            original_import = builtins.__import__

            def mock_import(name: str, *args, **kwargs):
                if name == "cognee":
                    raise ImportError("No module named 'cognee'")
                return original_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=mock_import):
                client = CogneeClient()
                result = await client.init()

            assert result is False
            assert client.is_available() is False

    @pytest.mark.asyncio
    async def test_reset_safe_when_unavailable(self) -> None:
        """Reset does not raise when Cognee is unavailable."""
        client = CogneeClient()
        # Client never initialized — reset should be safe
        await client.reset()  # Should not raise


class TestCogneeClientGracefulDegradation:
    @pytest.mark.asyncio
    async def test_investigation_continues_without_cognee(self) -> None:
        """Verify that when Cognee is disabled, the client reports unavailable."""
        with patch("app.cognee.client.get_settings") as mock_settings:
            mock_settings.return_value.cognee_enabled = False
            mock_settings.return_value.cognee_storage_path = "/tmp/cognee_test"
            mock_settings.return_value.cognee_model = "gpt-4o"
            mock_settings.return_value.openai_key = ""

            client = CogneeClient()
            await client.init()

            assert not client.is_available()
            # Reset should be safe even when unavailable
            await client.reset()

from __future__ import annotations

import logging

import httpx

from app.logging_utils import stage_tag

logger = logging.getLogger(__name__)


class HeraClient:
    """Thin wrapper around the Hera Motion REST API.

    Spec: https://docs.hera.video/llms.txt
        POST /videos                   submit a generation job
        GET  /videos/{video_id}        poll for status + file_url
        Auth: x-api-key header
        Status enum: in-progress | success | failed
    """

    def __init__(self, *, api_key: str, base_url: str) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        return {"x-api-key": self._api_key, "Content-Type": "application/json"}

    async def submit(self, spec: dict[str, object]) -> str:
        """Create a Hera video job. `spec` is whatever the Hera Agent produced.

        Required fields in spec: `prompt` (str), `outputs` (list).
        Optional: `duration_seconds`, `reference_image_url(s)`, `style_id`, etc.
        Returns the video_id of the queued job.
        """
        if "prompt" not in spec or "outputs" not in spec:
            raise ValueError("Hera spec must include 'prompt' and 'outputs'.")
        logger.info(
            "%s hera submit started (outputs=%d, prompt_chars=%d)",
            stage_tag("hera"),
            len(spec.get("outputs", [])) if isinstance(spec.get("outputs"), list) else 0,
            len(str(spec.get("prompt", ""))),
        )
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self._base_url}/videos", json=spec, headers=self._headers()
            )
            response.raise_for_status()
        data = response.json()
        video_id = data.get("video_id")
        if not isinstance(video_id, str) or not video_id:
            raise ValueError("Hera submit response missing video_id.")
        logger.info("%s hera submit finished (video_id=%s)", stage_tag("hera"), video_id)
        return video_id

    async def poll(self, video_id: str) -> dict[str, object]:
        """Get current status. Returns a normalized
        {status, file_url, error} dict regardless of how many outputs were
        configured. file_url is the first successful output's URL.
        """
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self._base_url}/videos/{video_id}", headers=self._headers()
            )
            response.raise_for_status()
        data = response.json()
        normalized = self._normalize_poll_response(data)
        logger.info(
            "%s hera poll finished (video_id=%s, status=%s, top_level_status=%s, file_url=%s)",
            stage_tag("hera"),
            video_id,
            normalized["status"],
            normalized["top_level_status"],
            bool(normalized["file_url"]),
        )
        return {
            "status": normalized["status"],
            "file_url": normalized["file_url"],
            "error": normalized["error"],
        }

    def _normalize_poll_response(self, data: dict[str, object]) -> dict[str, object]:
        top_level_status = str(data.get("status", "")).lower()
        outputs = data.get("outputs") or []
        status = top_level_status
        file_url: str | None = None
        error: str | None = None
        if isinstance(outputs, list) and outputs:
            first = outputs[0]
            if isinstance(first, dict):
                output_status = str(first.get("status", "")).lower()
                if isinstance(first.get("file_url"), str):
                    file_url = first["file_url"]
                if isinstance(first.get("error"), str):
                    error = first["error"]
                if output_status == "success" and file_url:
                    status = "success"
                elif output_status == "failed":
                    status = "failed"
                elif top_level_status not in {"success", "failed"} and output_status == "in-progress":
                    status = "in-progress"
        return {
            "status": status,
            "top_level_status": top_level_status,
            "file_url": file_url,
            "error": error,
        }

    async def download(self, url: str) -> bytes:
        # Guard against SSRF: the URL comes from a third-party API response,
        # so restrict to https:// and reject scheme-less / file:// / http://.
        if not isinstance(url, str) or not url.lower().startswith("https://"):
            raise ValueError("Hera download URL must be https://")
        logger.info("%s hera download started (url=%s)", stage_tag("hera"), url)
        async with httpx.AsyncClient(timeout=120, follow_redirects=False) as client:
            response = await client.get(url)
            response.raise_for_status()
        logger.info("%s hera download finished (bytes=%d)", stage_tag("hera"), len(response.content))
        return response.content

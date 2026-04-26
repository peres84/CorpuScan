from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.jobs import JobStore
from app.pipeline import render_hera_assets
from app.schemas import SourceKind


class FakeHeraClient:
    def __init__(self) -> None:
        self.submit_calls: list[dict[str, object]] = []
        self.download_calls: list[str] = []

    async def submit(self, spec: dict[str, object]) -> str:
        self.submit_calls.append(spec)
        return f"video-{len(self.submit_calls)}"

    async def download(self, url: str) -> bytes:
        self.download_calls.append(url)
        return url.encode("utf-8")


@pytest.mark.asyncio
async def test_render_hera_assets_reuses_existing_video_ids_after_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    job_store = JobStore()
    job_id = job_store.create(source_kind=SourceKind.PDF)
    client = FakeHeraClient()
    seen_video_ids: list[list[str]] = []
    poll_windows = {"count": 0}

    async def fake_poll_existing_hera_assets(**kwargs: object) -> None:
        hera_video_ids = kwargs["hera_video_ids"]
        completed = kwargs["completed"]
        seen_video_ids.append(list(hera_video_ids))  # type: ignore[arg-type]
        poll_windows["count"] += 1
        if poll_windows["count"] == 1:
            raise TimeoutError("slow render")
        completed[0] = "https://cdn.hera.video/intro.mp4"  # type: ignore[index]
        completed[1] = "https://cdn.hera.video/scene.mp4"  # type: ignore[index]

    monkeypatch.setattr("app.pipeline._poll_existing_hera_assets", fake_poll_existing_hera_assets)

    clips = await render_hera_assets(
        job_store=job_store,
        job_id=job_id,
        hera_client=client,  # type: ignore[arg-type]
        all_specs=[{"prompt": "intro", "outputs": []}, {"prompt": "scene", "outputs": []}],
        timeout_seconds=1,
        retry_attempts=3,
        poll_interval_seconds=0.1,
    )

    assert len(client.submit_calls) == 2
    assert seen_video_ids == [["video-1", "video-2"], ["video-1", "video-2"]]
    assert poll_windows["count"] == 2
    assert clips == [
        b"https://cdn.hera.video/intro.mp4",
        b"https://cdn.hera.video/scene.mp4",
    ]

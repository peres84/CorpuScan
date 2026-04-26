from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.jobs import JobStore
from app.pipeline import HeraRenderFailedError, render_hera_assets
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
async def test_render_hera_assets_resubmits_all_stuck_renders_after_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
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

    # Initial submit (2) + resubmit of both stuck renders after window 1 (2) = 4.
    assert len(client.submit_calls) == 4
    assert seen_video_ids == [["video-1", "video-2"], ["video-3", "video-4"]]
    assert poll_windows["count"] == 2
    assert clips == [
        b"https://cdn.hera.video/intro.mp4",
        b"https://cdn.hera.video/scene.mp4",
    ]


@pytest.mark.asyncio
async def test_render_hera_assets_only_resubmits_stuck_renders(monkeypatch: pytest.MonkeyPatch) -> None:
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
            # Index 0 finishes, index 1 is stuck.
            completed[0] = "https://cdn.hera.video/intro.mp4"  # type: ignore[index]
            raise TimeoutError("one render still stuck")
        # Window 2: stuck render finally finishes.
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

    # Initial submit (2) + resubmit of only the stuck render (1) = 3.
    assert len(client.submit_calls) == 3
    # Window 2 keeps video-1 (already done) and swaps video-2 -> video-3 (resubmitted).
    assert seen_video_ids == [["video-1", "video-2"], ["video-1", "video-3"]]
    assert poll_windows["count"] == 2
    assert clips == [
        b"https://cdn.hera.video/intro.mp4",
        b"https://cdn.hera.video/scene.mp4",
    ]


@pytest.mark.asyncio
async def test_render_hera_assets_resubmits_only_failed_render(monkeypatch: pytest.MonkeyPatch) -> None:
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
            # Index 0 succeeds; index 1 fails (Hera explicitly returns status=failed).
            completed[0] = "https://cdn.hera.video/intro.mp4"  # type: ignore[index]
            raise HeraRenderFailedError("idx=1: render exploded")
        # Window 2: resubmitted render finishes.
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

    # Initial submit (2) + resubmit of only the failed render (1) = 3.
    assert len(client.submit_calls) == 3
    # Window 2 keeps video-1 (already done) and swaps video-2 -> video-3 (resubmitted).
    assert seen_video_ids == [["video-1", "video-2"], ["video-1", "video-3"]]
    assert poll_windows["count"] == 2
    assert clips == [
        b"https://cdn.hera.video/intro.mp4",
        b"https://cdn.hera.video/scene.mp4",
    ]

from __future__ import annotations

import httpx


class HeraClient:
    def __init__(self, *, api_key: str, base_url: str) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    async def submit(self, spec: dict[str, object]) -> str:
        headers = {"Authorization": f"Bearer {self._api_key}"}
        payload = {"spec": spec}
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(f"{self._base_url}/renders", json=payload, headers=headers)
            response.raise_for_status()
        data = response.json()
        job_id = data.get("id") or data.get("job_id")
        if not isinstance(job_id, str) or not job_id:
            raise ValueError("Hera submit response missing job id.")
        return job_id

    async def poll(self, hera_job_id: str) -> dict[str, object]:
        headers = {"Authorization": f"Bearer {self._api_key}"}
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(f"{self._base_url}/renders/{hera_job_id}", headers=headers)
            response.raise_for_status()
        data = response.json()
        status = data.get("status")
        video_url = data.get("video_url") or data.get("url")
        return {"status": status, "video_url": video_url}

    async def download(self, url: str) -> bytes:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.get(url)
            response.raise_for_status()
        return response.content

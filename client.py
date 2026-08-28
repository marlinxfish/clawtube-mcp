"""Async HTTPX client ke clawtube-backend (REST di localhost:8080).

Implementasi penuh menyusul via implementation plan.
"""

import os

import httpx

BASE_URL = os.getenv("CLAWTUBE_API_URL", "http://localhost:8080")


class ClawTubeClient:
    """Client REST async ke backend ClawTube."""

    def __init__(self, base_url: str = BASE_URL, timeout: float = 30.0) -> None:
        self._http = httpx.AsyncClient(base_url=base_url, timeout=timeout)

    async def resolve(self, platform: str, input: str) -> dict:
        resp = await self._http.post(
            "/v1/resolve", json={"platform": platform, "input": input}
        )
        resp.raise_for_status()
        return resp.json()

    async def aclose(self) -> None:
        await self._http.aclose()

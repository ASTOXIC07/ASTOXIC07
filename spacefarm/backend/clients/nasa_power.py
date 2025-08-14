import asyncio
from datetime import date
from typing import Dict, Optional

import httpx


class NASAPowerClient:
    BASE_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"

    def __init__(self, timeout_seconds: int = 20):
        self._timeout = httpx.Timeout(timeout_seconds)
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def get_daily_precip_mm(self, latitude: float, longitude: float, start: date, end: date) -> Dict[str, float]:
        # PRECTOTCORR is in mm/day
        params = {
            "parameters": "PRECTOTCORR",
            "community": "AG",
            "latitude": f"{latitude:.4f}",
            "longitude": f"{longitude:.4f}",
            "start": start.strftime("%Y%m%d"),
            "end": end.strftime("%Y%m%d"),
            "format": "JSON",
        }
        client = await self._get_client()
        try:
            resp = await client.get(self.BASE_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
            series = data.get("properties", {}).get("parameter", {}).get("PRECTOTCORR", {})
            # Return dict of date_str -> mm value (float)
            return {k: float(v) for k, v in series.items() if v is not None}
        except Exception as exc:
            # In production, log this
            print(f"[NASAPowerClient] Error fetching data: {exc}")
            return {}


# Simple manual test
if __name__ == "__main__":
    async def _test():
        client = NASAPowerClient()
        today = date.today()
        start = today.replace(day=max(1, today.day - 7))
        data = await client.get_daily_precip_mm(38.58, -121.49, start, today)
        print("Sample: ", list(data.items())[:3])
        await client.close()

    asyncio.run(_test())
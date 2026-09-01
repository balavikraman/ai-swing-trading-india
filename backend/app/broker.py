from __future__ import annotations

import os
from dataclasses import dataclass

import requests


@dataclass(frozen=True)
class BrokerStatus:
    provider: str
    configured: bool
    read_only: bool = True
    authenticated: bool = False
    detail: str | None = None


class ZerodhaReadOnlyClient:
    """Read-only Kite Connect adapter. Intentionally exposes no order-placement methods."""

    base_url = "https://api.kite.trade"
    provider = "zerodha-kite"

    def __init__(self, api_key: str | None = None, access_token: str | None = None, timeout: float = 10):
        self.api_key = api_key or os.getenv("KITE_API_KEY")
        self.access_token = access_token or os.getenv("KITE_ACCESS_TOKEN")
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.access_token)

    def _headers(self) -> dict:
        if not self.configured:
            raise RuntimeError("Zerodha read-only credentials not configured")
        return {"X-Kite-Version": "3", "Authorization": f"token {self.api_key}:{self.access_token}"}

    def _get(self, path: str, params=None):
        response = requests.get(f"{self.base_url}{path}", headers=self._headers(), params=params, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") != "success":
            raise RuntimeError(payload.get("message", "Kite request failed"))
        return payload.get("data")

    def profile(self):
        return self._get("/user/profile")

    def holdings(self):
        return self._get("/portfolio/holdings")

    def positions(self):
        return self._get("/portfolio/positions")

    def margins(self):
        return self._get("/user/margins")

    def quotes(self, instruments: list[str]):
        if not instruments:
            return {}
        return self._get("/quote", params=[("i", instrument) for instrument in instruments])

    def ohlc(self, instruments: list[str]):
        if not instruments:
            return {}
        return self._get("/quote/ohlc", params=[("i", instrument) for instrument in instruments])

    def status(self) -> BrokerStatus:
        if not self.configured:
            return BrokerStatus(self.provider, False, True, False, "Set KITE_API_KEY and KITE_ACCESS_TOKEN")
        try:
            profile = self.profile()
            label = profile.get("user_name") or profile.get("user_id", "Zerodha user")
            return BrokerStatus(self.provider, True, True, True, f"Authenticated as {label}")
        except Exception as exc:
            return BrokerStatus(self.provider, True, True, False, str(exc))

"""CoinGecko REST and WebSocket access.

Plans / keys (set via environment variables, never commit keys):
  COINGECKO_API_KEY  your key (optional for REST, required for WebSocket)
  COINGECKO_PLAN     "public" (no key), "demo" (free Demo key) or "pro" (paid plans)

REST works without a key (rate limited). The WebSocket stream
(wss://stream.coingecko.com/v1, channel CGSimplePrice) needs a paid plan key.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, AsyncIterator

import requests

log = logging.getLogger(__name__)

PUBLIC_URL = "https://api.coingecko.com/api/v3"
PRO_URL = "https://pro-api.coingecko.com/api/v3"
WS_URL = "wss://stream.coingecko.com/v1"


class CoinGeckoError(RuntimeError):
    pass


class CoinGeckoClient:
    def __init__(
        self,
        api_key: str | None = None,
        plan: str | None = None,
        session: requests.Session | None = None,
        timeout: float = 15.0,
        max_retries: int = 4,
        sleep=time.sleep,
    ) -> None:
        self.sleep = sleep  # replaceable so a stop signal can interrupt back-off waits
        self.api_key = api_key if api_key is not None else os.getenv("COINGECKO_API_KEY") or None
        self.plan = (plan or os.getenv("COINGECKO_PLAN") or ("demo" if self.api_key else "public")).lower()
        if self.plan not in ("public", "demo", "pro"):
            raise ValueError(f"unknown CoinGecko plan {self.plan!r}")
        self.base_url = PRO_URL if self.plan == "pro" else PUBLIC_URL
        self.session = session or requests.Session()
        self.timeout = timeout
        self.max_retries = max_retries
        self.headers: dict[str, str] = {"accept": "application/json"}
        if self.api_key and self.plan != "public":
            header = "x-cg-pro-api-key" if self.plan == "pro" else "x-cg-demo-api-key"
            self.headers[header] = self.api_key

    def _get(self, path: str, params: dict[str, Any]) -> Any:
        url = f"{self.base_url}{path}"
        delay = 2.0
        for attempt in range(self.max_retries + 1):
            try:
                resp = self.session.get(url, params=params, headers=self.headers, timeout=self.timeout)
            except requests.RequestException as exc:
                if attempt == self.max_retries:
                    raise CoinGeckoError(f"request to {path} failed: {exc}") from exc
                log.warning("CoinGecko request error (%s), retrying in %.0fs", exc, delay)
            else:
                if resp.status_code == 429 or resp.status_code >= 500:
                    if attempt == self.max_retries:
                        raise CoinGeckoError(f"{path}: HTTP {resp.status_code} after {attempt + 1} tries")
                    retry_after = resp.headers.get("retry-after")
                    wait = float(retry_after) if retry_after and retry_after.isdigit() else delay
                    log.warning("CoinGecko HTTP %s, retrying in %.0fs", resp.status_code, wait)
                    self.sleep(wait)
                    delay = min(delay * 2, 60)
                    continue
                if resp.status_code >= 400:
                    raise CoinGeckoError(f"{path}: HTTP {resp.status_code}: {resp.text[:200]}")
                return resp.json()
            self.sleep(delay)
            delay = min(delay * 2, 60)
        raise CoinGeckoError(f"request to {path} failed")  # pragma: no cover

    def simple_price(self, coin_id: str = "bitcoin", vs: str = "usd") -> tuple[float, float]:
        """Current price and its timestamp (unix seconds)."""
        data = self._get(
            "/simple/price",
            {"ids": coin_id, "vs_currencies": vs, "include_last_updated_at": "true"},
        )
        try:
            entry = data[coin_id]
            return float(entry[vs]), float(entry.get("last_updated_at") or time.time())
        except (KeyError, TypeError, ValueError) as exc:
            raise CoinGeckoError(f"unexpected /simple/price response: {data!r}") from exc

    def market_chart(self, coin_id: str = "bitcoin", vs: str = "usd", days: int | float = 7) -> list[tuple[float, float]]:
        """Historical prices as (unix seconds, price).

        CoinGecko picks the granularity automatically: 1 day -> ~5 minutes,
        2-90 days -> hourly, more -> daily.
        """
        data = self._get(f"/coins/{coin_id}/market_chart", {"vs_currency": vs, "days": days})
        try:
            return [(float(ts) / 1000.0, float(p)) for ts, p in data["prices"] if p is not None]
        except (KeyError, TypeError, ValueError) as exc:
            raise CoinGeckoError("unexpected /market_chart response") from exc


def parse_ws_message(msg: Any, coin_id: str, vs: str) -> tuple[float, float] | None:
    """Extract (timestamp, price) from a CGSimplePrice stream message, else None.

    Price messages look like {"c": "C1", "i": "bitcoin", "vs": "usd", "p": 75836.1, "t": 1794006360, ...}.
    Control messages (welcome, ping, confirm_subscription) return None.
    """
    if not isinstance(msg, dict):
        return None
    payload = msg.get("message") if isinstance(msg.get("message"), dict) else msg
    if payload.get("c") != "C1" or payload.get("i") != coin_id:
        return None
    if payload.get("vs", vs) != vs:
        return None
    try:
        price = float(payload["p"])
    except (KeyError, TypeError, ValueError):
        return None
    ts = payload.get("t")
    try:
        ts = float(ts)
        if ts > 1e12:  # milliseconds
            ts /= 1000.0
    except (TypeError, ValueError):
        ts = time.time()
    return ts, price


async def stream_prices(coin_id: str, vs: str, api_key: str) -> AsyncIterator[tuple[float, float]]:
    """Yield (timestamp, price) ticks from the CoinGecko WebSocket (paid plan)."""
    import websockets

    identifier = json.dumps({"channel": "CGSimplePrice"})
    async with websockets.connect(WS_URL, additional_headers={"x-cg-pro-api-key": api_key}) as ws:
        await ws.send(json.dumps({"command": "subscribe", "identifier": identifier}))
        await ws.send(json.dumps({
            "command": "message",
            "identifier": identifier,
            "data": json.dumps({"coin_id": [coin_id], "action": "set_tokens"}),
        }))
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except (TypeError, ValueError):
                continue
            tick = parse_ws_message(msg, coin_id, vs)
            if tick is not None:
                yield tick

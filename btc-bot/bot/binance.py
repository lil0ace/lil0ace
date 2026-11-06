"""Historical candles from Binance's public market-data API (no key needed).

Used only for backtests: CoinGecko's free API has 5-minute data for the last 24 h only,
Binance serves years of 5-minute klines. Prices are BTC/USDT, which tracks BTC/USD closely.
Host: data-api.binance.vision (public market data mirror of api.binance.com).
"""

from __future__ import annotations

import logging
import time

import requests

from .candles import Candle

log = logging.getLogger(__name__)

BASE_URL = "https://data-api.binance.vision/api/v3/klines"
INTERVALS = {60: "1m", 180: "3m", 300: "5m", 900: "15m", 1800: "30m", 3600: "1h", 7200: "2h",
             14400: "4h", 21600: "6h", 28800: "8h", 43200: "12h", 86400: "1d"}
LIMIT = 1000


class BinanceError(RuntimeError):
    pass


def fetch_klines(
    symbol: str,
    interval: int,
    start: float,
    end: float | None = None,
    session: requests.Session | None = None,
    sleep=time.sleep,
) -> list[Candle]:
    """Completed candles with start time in [start, end), oldest first. Times in unix seconds."""
    if interval not in INTERVALS:
        raise ValueError(f"Binance has no {interval}s candles; use one of {sorted(INTERVALS)}")
    session = session or requests.Session()
    now = time.time()
    end = min(end if end is not None else now, now)
    cursor = int(start * 1000)
    end_ms = int(end * 1000)
    out: list[Candle] = []
    while cursor < end_ms:
        params = {"symbol": symbol.upper(), "interval": INTERVALS[interval],
                  "startTime": cursor, "endTime": end_ms - 1, "limit": LIMIT}
        for attempt in range(5):
            try:
                resp = session.get(BASE_URL, params=params, timeout=20)
            except requests.RequestException as exc:
                err = str(exc)
            else:
                if resp.status_code == 200:
                    break
                err = f"HTTP {resp.status_code}: {resp.text[:200]}"
                if resp.status_code not in (418, 429) and resp.status_code < 500:
                    raise BinanceError(err)
            log.warning("Binance request failed (%s), retrying", err)
            sleep(2 ** attempt)
        else:
            raise BinanceError(f"klines request failed: {err}")
        rows = resp.json()
        if not rows:
            break
        for r in rows:
            open_ms, close_ms = int(r[0]), int(r[6])
            if close_ms >= now * 1000:  # still running
                continue
            out.append(Candle(open_ms // 1000, float(r[1]), float(r[2]), float(r[3]), float(r[4])))
        cursor = int(rows[-1][0]) + interval * 1000
    return out

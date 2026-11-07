"""Forward testing (paper trading) on live CoinGecko prices.

Two price sources:
  rest  polls /simple/price (free, no key; CoinGecko refreshes roughly every 20-60 s)
  ws    CoinGecko WebSocket, sub-second ticks -> 1 s candles (needs a paid-plan API key)
"""

from __future__ import annotations

import asyncio
import logging
import math
import random
import signal
import threading
import time
from pathlib import Path

from .candles import CandleAggregator, resample
from .coingecko import CoinGeckoClient, CoinGeckoError, stream_prices
from .config import MarketConfig
from .engine import TradingEngine
from .state import read_json, write_json

log = logging.getLogger(__name__)


class PaperTrader:
    def __init__(
        self,
        engine: TradingEngine,
        candle_seconds: int,
        market: MarketConfig,
        state_path: str | Path,
        account_path: str | Path,
        source: str,
        state_every: float = 1.0,
    ) -> None:
        self.engine = engine
        self.agg = CandleAggregator(candle_seconds)
        tcfg = engine.trend_cfg
        self.trend_agg = CandleAggregator(tcfg.interval) if tcfg.enabled else None
        self.market = market
        self.state_path = Path(state_path)
        self.account_path = Path(account_path)
        self.source = source
        self.state_every = state_every
        self._last_state_write = 0.0
        self.status = "starting"
        self.last_error: str | None = None
        self.ticks = 0
        self.started_at = time.time()

    def load_account(self) -> bool:
        snap = read_json(self.account_path)
        if not snap:
            return False
        self.engine.restore_account(snap)
        log.info("resumed paper account: cash=%.2f qty=%.6f trades=%d",
                 self.engine.broker.cash, self.engine.broker.qty, len(self.engine.broker.trades))
        return True

    def warmup(self, client: CoinGeckoClient) -> None:
        """Prime the moving averages with recent history so trading can start right away."""
        now = time.time()
        if self.trend_agg is not None:
            tcfg = self.engine.trend_cfg
            days = min(90, max(2, math.ceil((tcfg.slow + 3) * tcfg.interval / 86400) + 1))
            points = client.market_chart(self.market.coin_id, self.market.vs_currency, days)
            candles = resample(points, tcfg.interval)
            for c in candles:
                if c.start + tcfg.interval <= now:
                    self.engine.on_trend_candle(c)
                else:
                    self.trend_agg.current = c  # the still-running trend candle
            log.info("trend warm-up: %d candles of %ss, trend now %s",
                     len(candles), tcfg.interval, self.engine.trend.state or "unknown")

        if self.agg.seconds < 300:
            log.info("no warm-up for %ss candles; waiting for enough live candles", self.agg.seconds)
            return
        # Prefer real OHLC candles from Binance (Supertrend needs true highs/lows); fall back to CoinGecko.
        try:
            from .binance import INTERVALS, fetch_klines
            if self.agg.seconds in INTERVALS and self.market.binance_symbol:
                candles = fetch_klines(self.market.binance_symbol, self.agg.seconds, now - 250 * self.agg.seconds, now)
                for c in candles:
                    self.engine.warmup(c)
                log.info("warm-up with %d Binance candles done", len(candles))
                return
        except Exception as exc:  # network, unknown symbol, ...
            log.warning("Binance warm-up failed (%s), using CoinGecko", exc)
        days = 1 if self.agg.seconds < 3600 else 30
        points = client.market_chart(self.market.coin_id, self.market.vs_currency, days)
        candles = resample(points, self.agg.seconds)
        n = 0
        for c in candles:
            if c.start + self.agg.seconds <= now:
                self.engine.warmup(c)
                n += 1
            else:
                self.agg.current = c
        log.info("warm-up with %d historical candles done", n)

    def on_tick(self, ts: float, price: float) -> None:
        self.ticks += 1
        if self.trend_agg is not None:
            for tc in self.trend_agg.add(ts, price):
                before = self.engine.trend.state
                self.engine.on_trend_candle(tc)
                if self.engine.trend.state != before:
                    log.info("higher-timeframe trend changed: %s -> %s", before, self.engine.trend.state)
        for candle in self.agg.add(ts, price):
            for tr in self.engine.on_candle(candle):
                pnl = f" pnl={tr.pnl:+.2f}" if tr.pnl is not None else ""
                log.info("PAPER %s %.6f @ %.2f (%s, trend %s)%s", tr.side.upper(), tr.qty, tr.price, tr.reason, tr.trend, pnl)
            self.save_account()
        self.engine.mark(ts, price)
        self.write_state()

    def save_account(self) -> None:
        write_json(self.account_path, self.engine.account_snapshot())

    def write_state(self, force: bool = False) -> None:
        now = time.time()
        if not force and now - self._last_state_write < self.state_every:
            return
        self._last_state_write = now
        cur = self.agg.current
        write_json(self.state_path, self.engine.to_state(
            mode="paper",
            source=self.source,
            status=self.status,
            last_error=self.last_error,
            coin=self.market.coin_id,
            vs=self.market.vs_currency,
            candle_seconds=self.agg.seconds,
            ticks=self.ticks,
            started_at=self.started_at,
            updated_at=now,
            open_candle=cur.to_dict() if cur else None,
            trend_open_candle=self.trend_agg.current.to_dict() if self.trend_agg and self.trend_agg.current else None,
        ))


def _install_stop_handlers(stop: threading.Event) -> None:
    def handler(signum, _frame):
        log.info("signal %s received, stopping", signum)
        stop.set()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, handler)
        except ValueError:  # not in main thread
            pass


def run_rest(trader: PaperTrader, client: CoinGeckoClient, poll_seconds: float, stop: threading.Event | None = None) -> None:
    stop = stop or threading.Event()
    _install_stop_handlers(stop)
    client.sleep = stop.wait  # Ctrl+C / SIGTERM also cuts rate-limit back-off short
    trader.status = "running"
    while not stop.is_set():
        try:
            price, _updated = client.simple_price(trader.market.coin_id, trader.market.vs_currency)
            trader.last_error = None
            trader.on_tick(time.time(), price)
        except CoinGeckoError as exc:
            trader.last_error = str(exc)
            log.warning("price fetch failed: %s", exc)
            trader.write_state(force=True)
        stop.wait(poll_seconds)
    trader.status = "stopped"
    trader.save_account()
    trader.write_state(force=True)


def run_ws(trader: PaperTrader, api_key: str, stop: threading.Event | None = None) -> None:
    stop = stop or threading.Event()
    _install_stop_handlers(stop)

    async def main() -> None:
        backoff = 1.0
        while not stop.is_set():
            try:
                trader.status = "connecting"
                trader.write_state(force=True)
                async for ts, price in stream_prices(trader.market.coin_id, trader.market.vs_currency, api_key):
                    trader.status = "running"
                    trader.last_error = None
                    backoff = 1.0
                    trader.on_tick(ts, price)
                    if stop.is_set():
                        return
                raise ConnectionError("stream closed")
            except Exception as exc:  # reconnect on anything network related
                if stop.is_set():
                    return
                trader.status = "reconnecting"
                trader.last_error = f"{type(exc).__name__}: {exc}"
                log.warning("websocket error (%s), reconnecting in %.0fs", trader.last_error, backoff)
                trader.write_state(force=True)
                await asyncio.sleep(backoff + random.random())
                backoff = min(backoff * 2, 60)

    try:
        asyncio.run(main())
    finally:
        trader.status = "stopped"
        trader.save_account()
        trader.write_state(force=True)

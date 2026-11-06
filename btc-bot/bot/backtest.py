"""Backtests on CoinGecko history."""

from __future__ import annotations

import csv
import math
import time
from dataclasses import asdict, replace
from pathlib import Path

from .candles import Candle, resample
from .coingecko import CoinGeckoClient
from .config import MarketConfig, RiskConfig, StrategyConfig, TrendConfig
from .engine import TradingEngine


def _completed(candles: list[Candle], interval: int, now: float | None = None) -> list[Candle]:
    now = time.time() if now is None else now
    return [c for c in candles if c.start + interval <= now]


def fetch_history(client: CoinGeckoClient, market: MarketConfig, days: float, interval: int) -> list[Candle]:
    if interval < 3600 and days > 1:
        raise ValueError(
            "CoinGecko only returns 5-minute data for the last 24 hours (days 2-90 are hourly). "
            "Use --days 1 for 5-minute candles."
        )
    points = client.market_chart(market.coin_id, market.vs_currency, days)
    return _completed(resample(points, interval), interval)


def fetch_trend_history(client: CoinGeckoClient, market: MarketConfig, trend: TrendConfig, days: float) -> list[Candle]:
    """Higher-timeframe candles covering the backtest plus enough warm-up for the slow MA."""
    warmup_days = (trend.slow + 3) * trend.interval / 86400
    span = min(90, max(2, math.ceil(days + warmup_days)))  # >= 2 days -> hourly data
    points = client.market_chart(market.coin_id, market.vs_currency, span)
    return _completed(resample(points, trend.interval), trend.interval)


def run_backtest(
    candles: list[Candle],
    strategy_cfg: StrategyConfig,
    risk_cfg: RiskConfig,
    trend_cfg: TrendConfig | None = None,
    trend_candles: list[Candle] | None = None,
    interval: int | None = None,
) -> TradingEngine:
    """Replay candles. A trend candle is only used once it has closed (no look-ahead)."""
    engine = TradingEngine(strategy_cfg, risk_cfg, history_limit=max(len(candles), 1), trend_cfg=trend_cfg)
    if interval is None:
        interval = int(candles[1].start - candles[0].start) if len(candles) > 1 else 60
    pending = sorted(trend_candles or [], key=lambda c: c.start)
    tcfg = engine.trend_cfg
    i = 0
    for c in candles:
        close_time = c.start + interval
        while tcfg.enabled and i < len(pending) and pending[i].start + tcfg.interval <= close_time:
            engine.on_trend_candle(pending[i])
            i += 1
        engine.on_candle(c)
    return engine


def sweep(
    candles: list[Candle],
    strategy_cfg: StrategyConfig,
    risk_cfg: RiskConfig,
    fasts: list[int],
    slows: list[int],
    trend_cfg: TrendConfig | None = None,
    trend_candles: list[Candle] | None = None,
    interval: int | None = None,
) -> list[dict]:
    """Try several fast/slow pairs. A good strategy should work across neighbours, not just one combo."""
    rows = []
    for f in fasts:
        for s in slows:
            if f >= s:
                continue
            eng = run_backtest(candles, replace(strategy_cfg, fast=f, slow=s), risk_cfg, trend_cfg, trend_candles, interval)
            rows.append({"fast": f, "slow": s, **eng.metrics()})
    rows.sort(key=lambda r: r["total_return_pct"], reverse=True)
    return rows


def write_trades_csv(engine: TradingEngine, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    trades = [asdict(t) for t in engine.broker.trades]
    with open(path, "w", newline="") as fh:
        fields = ["time", "side", "price", "qty", "fee", "reason", "pnl", "pnl_pct", "trend"]
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(trades)

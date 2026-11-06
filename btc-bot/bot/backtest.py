"""Backtests on CoinGecko history."""

from __future__ import annotations

import csv
from dataclasses import asdict, replace
from pathlib import Path

from .candles import Candle, resample
from .coingecko import CoinGeckoClient
from .config import MarketConfig, RiskConfig, StrategyConfig
from .engine import TradingEngine


def fetch_history(client: CoinGeckoClient, market: MarketConfig, days: float, interval: int) -> list[Candle]:
    points = client.market_chart(market.coin_id, market.vs_currency, days)
    candles = resample(points, interval)
    return candles[:-1] if len(candles) > 1 else candles  # drop the unfinished last candle


def run_backtest(candles: list[Candle], strategy_cfg: StrategyConfig, risk_cfg: RiskConfig) -> TradingEngine:
    engine = TradingEngine(strategy_cfg, risk_cfg, history_limit=max(len(candles), 1))
    for c in candles:
        engine.on_candle(c)
    return engine


def sweep(
    candles: list[Candle],
    strategy_cfg: StrategyConfig,
    risk_cfg: RiskConfig,
    fasts: list[int],
    slows: list[int],
) -> list[dict]:
    """Try several fast/slow pairs. A good strategy should work across neighbours, not just one combo."""
    rows = []
    for f in fasts:
        for s in slows:
            if f >= s:
                continue
            m = run_backtest(candles, replace(strategy_cfg, fast=f, slow=s), risk_cfg).metrics()
            rows.append({"fast": f, "slow": s, **m})
    rows.sort(key=lambda r: r["total_return_pct"], reverse=True)
    return rows


def write_trades_csv(engine: TradingEngine, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    trades = [asdict(t) for t in engine.broker.trades]
    with open(path, "w", newline="") as fh:
        fields = ["time", "side", "price", "qty", "fee", "reason", "pnl", "pnl_pct"]
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(trades)

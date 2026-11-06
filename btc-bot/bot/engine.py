"""Glue between strategy, higher-timeframe trend filter, risk rules and the paper account.

Rules (trend filter enabled, default):
  4h bullish:  5-min golden cross -> open long;  5-min death cross  -> close long
  4h bearish:  5-min death cross  -> open short; 5-min golden cross -> close short
A cross always flattens a position against it, whatever the trend; new entries are only
taken in the trend's direction. With the filter disabled the bot trades long-only on every cross.

Backtest and live paper trading use the very same engine, so forward-test
results are directly comparable to the backtest.
"""

from __future__ import annotations

from collections import deque
from dataclasses import asdict

from .broker import PaperBroker, Trade
from .candles import Candle
from .config import RiskConfig, StrategyConfig, TrendConfig
from .strategy import MACrossover


class TrendFilter:
    """Fast/slow moving averages on completed higher-timeframe candles."""

    def __init__(self, cfg: TrendConfig) -> None:
        cfg.validate()
        self.cfg = cfg
        self.ma = MACrossover(cfg.strategy())
        self.last_close_time: float | None = None  # end of the last completed trend candle
        self.candles: deque[dict] = deque(maxlen=500)

    @property
    def state(self) -> str | None:
        """"bull", "bear" or None (not enough data yet)."""
        if not self.cfg.enabled:
            return None
        if not self.ma.ready:
            return None
        if self.ma.fast > self.ma.slow:
            return "bull"
        if self.ma.fast < self.ma.slow:
            return "bear"
        return None

    def update(self, candle: Candle) -> None:
        if self.last_close_time is not None and candle.start + self.cfg.interval <= self.last_close_time:
            return  # already seen (e.g. warm-up overlap)
        self.ma.update(candle.close)
        self.last_close_time = candle.start + self.cfg.interval
        self.candles.append({"t": candle.start, "c": candle.close, "fast": self.ma.fast,
                             "slow": self.ma.slow, "trend": self.state})


class TradingEngine:
    def __init__(
        self,
        strategy_cfg: StrategyConfig,
        risk_cfg: RiskConfig,
        broker: PaperBroker | None = None,
        history_limit: int = 2000,
        trend_cfg: TrendConfig | None = None,
    ) -> None:
        risk_cfg.validate()
        self.strategy_cfg = strategy_cfg
        self.risk = risk_cfg
        self.trend_cfg = trend_cfg or TrendConfig(enabled=False)
        self.trend = TrendFilter(self.trend_cfg)
        self.strategy = MACrossover(strategy_cfg)
        self.broker = broker or PaperBroker(
            starting_cash=risk_cfg.starting_cash,
            fee_rate=risk_cfg.fee_rate,
            slippage=risk_cfg.slippage,
            position_fraction=risk_cfg.position_fraction,
        )
        self.peak_equity = self.broker.starting_cash
        self.max_drawdown = 0.0
        self.halted = False
        self.halt_reason: str | None = None
        self.candles: deque[dict] = deque(maxlen=history_limit)
        self.equity_curve: deque[tuple[float, float]] = deque(maxlen=history_limit)
        self.first_price: float | None = None
        self.last_price: float | None = None
        self.last_time: float | None = None
        self.candle_count = 0

    # -- feeding data -------------------------------------------------------
    def on_trend_candle(self, candle: Candle) -> None:
        """Feed one *completed* higher-timeframe candle (e.g. 4h)."""
        self.trend.update(candle)

    def warmup(self, candle: Candle) -> None:
        """Feed history to the moving averages without trading."""
        self.strategy.update(candle.close)
        self._record_candle(candle)

    def on_candle(self, candle: Candle) -> list[Trade]:
        price, t = candle.close, float(candle.start)
        if self.first_price is None:
            self.first_price = price
        self.candle_count += 1
        trades: list[Trade | None] = []
        signal = self.strategy.update(price)
        trend = self.trend.state
        b = self.broker

        # 1) protective exits
        if b.in_position and b.entry_price:
            sl, tp = self.risk.stop_loss_pct, self.risk.take_profit_pct
            move = (price / b.entry_price - 1) * (1 if b.is_long else -1)  # + = in our favour
            if sl and move <= -sl:
                trades.append(b.close(price, t, "stop_loss", trend))
            elif tp and move >= tp:
                trades.append(b.close(price, t, "take_profit", trend))

        # 2) signal exits: a cross against the position flattens it
        if signal == "sell" and b.is_long:
            trades.append(b.close(price, t, "death_cross", trend))
        elif signal == "buy" and b.is_short:
            trades.append(b.close(price, t, "golden_cross", trend))

        # 3) entries, only in the direction of the higher-timeframe trend
        if not self.halted and not b.in_position:
            if not self.trend_cfg.enabled:
                if signal == "buy":
                    trades.append(b.buy(price, t, "golden_cross"))
            elif signal == "buy" and trend == "bull":
                trades.append(b.buy(price, t, "golden_cross", trend))
            elif signal == "sell" and trend == "bear" and self.trend_cfg.allow_short:
                trades.append(b.short(price, t, "death_cross", trend))

        # 4) account-level kill switch
        equity = b.equity(price)
        self.peak_equity = max(self.peak_equity, equity)
        dd = 1 - equity / self.peak_equity if self.peak_equity > 0 else 0.0
        self.max_drawdown = max(self.max_drawdown, dd)
        if not self.halted and dd >= self.risk.max_drawdown_pct:
            if b.in_position:
                trades.append(b.close(price, t, "kill_switch", trend))
            self.halted = True
            self.halt_reason = f"drawdown {dd:.1%} >= limit {self.risk.max_drawdown_pct:.0%}"

        self._record_candle(candle, signal, trend)
        self.equity_curve.append((t, b.equity(price)))
        self.last_price, self.last_time = price, t
        return [tr for tr in trades if tr is not None]

    def mark(self, t: float, price: float) -> None:
        """Live price update between candle closes (display only, no trading)."""
        self.last_price, self.last_time = price, t

    def _record_candle(self, candle: Candle, signal: str | None = None, trend: str | None = None) -> None:
        self.candles.append({
            "t": candle.start, "o": candle.open, "h": candle.high, "l": candle.low, "c": candle.close,
            "fast": self.strategy.fast, "slow": self.strategy.slow, "signal": signal, "trend": trend,
        })

    # -- reporting ----------------------------------------------------------
    def metrics(self) -> dict:
        b = self.broker
        price = self.last_price or 0.0
        equity = b.equity(price) if price else b.cash + b.cost_basis
        closes = [t for t in b.trades if t.side in ("sell", "cover")]
        wins = [t for t in closes if (t.pnl or 0) > 0]
        bh = (price / self.first_price - 1) if self.first_price and price else None
        return {
            "equity": equity,
            "cash": b.cash,
            "position_side": b.side if b.in_position else None,
            "position_qty": b.qty,
            "entry_price": b.entry_price,
            "unrealized_pnl": (b.position_value(price) - b.cost_basis) if b.in_position and price else 0.0,
            "total_return_pct": equity / b.starting_cash - 1,
            "buy_hold_return_pct": bh,
            "max_drawdown_pct": self.max_drawdown,
            "round_trips": len(closes),
            "long_trades": sum(1 for t in closes if t.side == "sell"),
            "short_trades": sum(1 for t in closes if t.side == "cover"),
            "win_rate": len(wins) / len(closes) if closes else None,
            "total_fees": sum(t.fee for t in b.trades),
            "realized_pnl": sum(t.pnl or 0 for t in closes),
            "trend": self.trend.state,
            "trend_fast": self.trend.ma.fast,
            "trend_slow": self.trend.ma.slow,
            "halted": self.halted,
            "halt_reason": self.halt_reason,
            "candles_processed": self.candle_count,
        }

    def to_state(self, **meta) -> dict:
        return {
            **meta,
            "strategy": asdict(self.strategy_cfg),
            "trend_filter": asdict(self.trend_cfg),
            "risk": asdict(self.risk),
            "last_price": self.last_price,
            "last_time": self.last_time,
            "metrics": self.metrics(),
            "candles": list(self.candles),
            "trend_candles": list(self.trend.candles),
            "equity": [{"t": t, "v": v} for t, v in self.equity_curve],
            "trades": [asdict(t) for t in self.broker.trades],
        }

    # -- persistence of the paper account (survives restarts) ---------------
    def account_snapshot(self) -> dict:
        return {
            "broker": self.broker.to_dict(),
            "peak_equity": self.peak_equity,
            "max_drawdown": self.max_drawdown,
            "halted": self.halted,
            "halt_reason": self.halt_reason,
            "first_price": self.first_price,
        }

    def restore_account(self, snap: dict) -> None:
        self.broker = PaperBroker.from_dict(snap["broker"])
        self.peak_equity = snap.get("peak_equity", self.broker.starting_cash)
        self.max_drawdown = snap.get("max_drawdown", 0.0)
        self.halted = snap.get("halted", False)
        self.halt_reason = snap.get("halt_reason")
        self.first_price = snap.get("first_price")

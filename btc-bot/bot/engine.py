"""Glue between strategy, risk rules and the paper account.

Backtest and live paper trading use the very same engine, so forward-test
results are directly comparable to the backtest.
"""

from __future__ import annotations

from collections import deque
from dataclasses import asdict

from .broker import PaperBroker, Trade
from .candles import Candle
from .config import RiskConfig, StrategyConfig
from .strategy import MACrossover


class TradingEngine:
    def __init__(
        self,
        strategy_cfg: StrategyConfig,
        risk_cfg: RiskConfig,
        broker: PaperBroker | None = None,
        history_limit: int = 2000,
    ) -> None:
        risk_cfg.validate()
        self.strategy_cfg = strategy_cfg
        self.risk = risk_cfg
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
    def warmup(self, candle: Candle) -> None:
        """Feed history to the moving averages without trading."""
        self.strategy.update(candle.close)
        self._record_candle(candle)

    def on_candle(self, candle: Candle) -> list[Trade]:
        price, t = candle.close, float(candle.start)
        if self.first_price is None:
            self.first_price = price
        self.candle_count += 1
        trades: list[Trade] = []
        signal = self.strategy.update(price)
        b = self.broker

        if b.in_position and b.entry_price:
            sl, tp = self.risk.stop_loss_pct, self.risk.take_profit_pct
            if sl and price <= b.entry_price * (1 - sl):
                trades.append(b.sell(price, t, "stop_loss"))
            elif tp and price >= b.entry_price * (1 + tp):
                trades.append(b.sell(price, t, "take_profit"))

        if not self.halted:
            if signal == "buy" and not b.in_position:
                trades.append(b.buy(price, t, "golden_cross"))
            elif signal == "sell" and b.in_position:
                trades.append(b.sell(price, t, "death_cross"))

        equity = b.equity(price)
        self.peak_equity = max(self.peak_equity, equity)
        dd = 1 - equity / self.peak_equity if self.peak_equity > 0 else 0.0
        self.max_drawdown = max(self.max_drawdown, dd)
        if not self.halted and dd >= self.risk.max_drawdown_pct:
            if b.in_position:
                trades.append(b.sell(price, t, "kill_switch"))
            self.halted = True
            self.halt_reason = f"drawdown {dd:.1%} >= limit {self.risk.max_drawdown_pct:.0%}"

        self._record_candle(candle, signal)
        self.equity_curve.append((t, b.equity(price)))
        self.last_price, self.last_time = price, t
        return [tr for tr in trades if tr is not None]

    def mark(self, t: float, price: float) -> None:
        """Live price update between candle closes (display only, no trading)."""
        self.last_price, self.last_time = price, t

    def _record_candle(self, candle: Candle, signal: str | None = None) -> None:
        self.candles.append({
            "t": candle.start, "o": candle.open, "h": candle.high, "l": candle.low, "c": candle.close,
            "fast": self.strategy.fast, "slow": self.strategy.slow, "signal": signal,
        })

    # -- reporting ----------------------------------------------------------
    def metrics(self) -> dict:
        b = self.broker
        price = self.last_price or 0.0
        equity = b.equity(price) if price else b.cash
        sells = [t for t in b.trades if t.side == "sell"]
        wins = [t for t in sells if (t.pnl or 0) > 0]
        bh = (price / self.first_price - 1) if self.first_price and price else None
        return {
            "equity": equity,
            "cash": b.cash,
            "position_qty": b.qty,
            "entry_price": b.entry_price,
            "total_return_pct": equity / b.starting_cash - 1,
            "buy_hold_return_pct": bh,
            "max_drawdown_pct": self.max_drawdown,
            "round_trips": len(sells),
            "win_rate": len(wins) / len(sells) if sells else None,
            "total_fees": sum(t.fee for t in b.trades),
            "realized_pnl": sum(t.pnl or 0 for t in sells),
            "halted": self.halted,
            "halt_reason": self.halt_reason,
            "candles_processed": self.candle_count,
        }

    def to_state(self, **meta) -> dict:
        return {
            **meta,
            "strategy": asdict(self.strategy_cfg),
            "risk": asdict(self.risk),
            "last_price": self.last_price,
            "last_time": self.last_time,
            "metrics": self.metrics(),
            "candles": list(self.candles),
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

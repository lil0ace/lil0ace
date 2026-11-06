"""Simulated account with long and short positions, fees and slippage. No real orders are ever sent.

Shorts are simulated like a margin/futures short without leverage: the entry amount is
set aside as collateral, profit = qty * (entry - exit). Funding/borrow costs are ignored.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Trade:
    time: float
    side: str          # "buy" (open long), "sell" (close long), "short" (open short), "cover" (close short)
    price: float       # fill price incl. slippage
    qty: float
    fee: float
    reason: str
    pnl: float | None = None      # realised P&L of the round trip (closing trades only)
    pnl_pct: float | None = None
    trend: str | None = None      # higher-timeframe trend at the time of the trade


@dataclass
class PaperBroker:
    starting_cash: float = 10_000.0
    fee_rate: float = 0.001
    slippage: float = 0.0005
    position_fraction: float = 1.0
    cash: float = field(default=-1.0)
    qty: float = 0.0
    side: str | None = None        # "long", "short" or None (flat)
    entry_price: float | None = None
    cost_basis: float = 0.0        # cash committed at entry, incl. entry fee
    trades: list[Trade] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.cash < 0:
            self.cash = self.starting_cash
        if self.qty > 0 and self.side is None:  # account files from the long-only version
            self.side = "long"

    @property
    def in_position(self) -> bool:
        return self.qty > 0

    @property
    def is_long(self) -> bool:
        return self.in_position and self.side == "long"

    @property
    def is_short(self) -> bool:
        return self.in_position and self.side == "short"

    def position_value(self, price: float) -> float:
        if not self.in_position:
            return 0.0
        if self.side == "short":
            return self.qty * (2 * self.entry_price - price)
        return self.qty * price

    def equity(self, price: float) -> float:
        return self.cash + self.position_value(price)

    def _open(self, side: str, price: float, t: float, reason: str, trend: str | None) -> Trade | None:
        if self.in_position or self.cash <= 0:
            return None
        spend = self.cash * self.position_fraction
        fill = price * (1 + self.slippage) if side == "long" else price * (1 - self.slippage)
        fee = spend * self.fee_rate
        self.qty = (spend - fee) / fill
        self.cash -= spend
        self.side = side
        self.entry_price = fill
        self.cost_basis = spend
        trade = Trade(t, "buy" if side == "long" else "short", fill, self.qty, fee, reason, trend=trend)
        self.trades.append(trade)
        return trade

    def _close(self, price: float, t: float, reason: str, trend: str | None) -> Trade | None:
        if not self.in_position:
            return None
        if self.side == "short":
            fill = price * (1 + self.slippage)
            gross = self.qty * (2 * self.entry_price - fill)
            fee = self.qty * fill * self.fee_rate
            side = "cover"
        else:
            fill = price * (1 - self.slippage)
            gross = self.qty * fill
            fee = gross * self.fee_rate
            side = "sell"
        proceeds = gross - fee
        pnl = proceeds - self.cost_basis
        trade = Trade(t, side, fill, self.qty, fee, reason, pnl,
                      pnl / self.cost_basis if self.cost_basis else None, trend)
        self.cash += proceeds
        self.qty = 0.0
        self.side = None
        self.entry_price = None
        self.cost_basis = 0.0
        self.trades.append(trade)
        return trade

    def buy(self, price: float, t: float, reason: str = "signal", trend: str | None = None) -> Trade | None:
        """Open a long."""
        return self._open("long", price, t, reason, trend)

    def short(self, price: float, t: float, reason: str = "signal", trend: str | None = None) -> Trade | None:
        """Open a short."""
        return self._open("short", price, t, reason, trend)

    def close(self, price: float, t: float, reason: str = "signal", trend: str | None = None) -> Trade | None:
        """Flatten whatever position is open."""
        return self._close(price, t, reason, trend)

    def sell(self, price: float, t: float, reason: str = "signal", trend: str | None = None) -> Trade | None:
        """Close a long (no-op when flat or short)."""
        return self._close(price, t, reason, trend) if self.is_long else None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "PaperBroker":
        trades = [Trade(**t) for t in d.get("trades", [])]
        fields = {k: v for k, v in d.items() if k != "trades"}
        return cls(**fields, trades=trades)

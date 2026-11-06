"""Simulated spot account (long only) with fees and slippage. No real orders are ever sent."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Trade:
    time: float
    side: str          # "buy" or "sell"
    price: float       # fill price incl. slippage
    qty: float
    fee: float
    reason: str
    pnl: float | None = None      # realised P&L of the round trip (sells only)
    pnl_pct: float | None = None


@dataclass
class PaperBroker:
    starting_cash: float = 10_000.0
    fee_rate: float = 0.001
    slippage: float = 0.0005
    position_fraction: float = 1.0
    cash: float = field(default=-1.0)
    qty: float = 0.0
    entry_price: float | None = None
    cost_basis: float = 0.0
    trades: list[Trade] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.cash < 0:
            self.cash = self.starting_cash

    @property
    def in_position(self) -> bool:
        return self.qty > 0

    def equity(self, price: float) -> float:
        return self.cash + self.qty * price

    def buy(self, price: float, t: float, reason: str = "signal") -> Trade | None:
        if self.in_position or self.cash <= 0:
            return None
        spend = self.cash * self.position_fraction
        fill = price * (1 + self.slippage)
        fee = spend * self.fee_rate
        qty = (spend - fee) / fill
        self.cash -= spend
        self.qty = qty
        self.entry_price = fill
        self.cost_basis = spend
        trade = Trade(t, "buy", fill, qty, fee, reason)
        self.trades.append(trade)
        return trade

    def sell(self, price: float, t: float, reason: str = "signal") -> Trade | None:
        if not self.in_position:
            return None
        fill = price * (1 - self.slippage)
        gross = self.qty * fill
        fee = gross * self.fee_rate
        proceeds = gross - fee
        pnl = proceeds - self.cost_basis
        trade = Trade(t, "sell", fill, self.qty, fee, reason, pnl, pnl / self.cost_basis if self.cost_basis else None)
        self.cash += proceeds
        self.qty = 0.0
        self.entry_price = None
        self.cost_basis = 0.0
        self.trades.append(trade)
        return trade

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "PaperBroker":
        trades = [Trade(**t) for t in d.get("trades", [])]
        fields = {k: v for k, v in d.items() if k != "trades"}
        return cls(**fields, trades=trades)

"""Default settings. Everything can be overridden on the command line."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StrategyConfig:
    fast: int = 9
    slow: int = 21
    kind: str = "sma"  # "sma" or "ema"

    def validate(self) -> None:
        if self.kind not in ("sma", "ema"):
            raise ValueError(f"unknown moving average kind: {self.kind!r}")
        if not (1 <= self.fast < self.slow):
            raise ValueError(f"need 1 <= fast < slow, got fast={self.fast} slow={self.slow}")


@dataclass
class TrendConfig:
    """Higher-timeframe filter. Bullish = fast MA above slow MA on completed trend candles."""

    enabled: bool = True
    interval: int = 4 * 3600   # 4h candles
    fast: int = 9
    slow: int = 21
    kind: str = "ema"
    allow_short: bool = True   # open shorts on death crosses in a bearish trend

    def strategy(self) -> StrategyConfig:
        return StrategyConfig(fast=self.fast, slow=self.slow, kind=self.kind)

    def validate(self) -> None:
        if self.enabled:
            if self.interval < 60:
                raise ValueError("trend interval must be >= 60 seconds")
            self.strategy().validate()


@dataclass
class RiskConfig:
    starting_cash: float = 10_000.0   # the "$10K challenge"
    fee_rate: float = 0.001           # 0.1 % per fill, typical spot taker fee
    slippage: float = 0.0005          # 0.05 % worse fill than the signal price
    position_fraction: float = 1.0    # share of cash used per entry
    stop_loss_pct: float | None = 0.03      # exit if price moves 3 % against the entry
    take_profit_pct: float | None = None    # optional fixed take-profit (both directions)
    max_drawdown_pct: float = 0.20    # kill switch: stop trading after -20 % from peak equity

    def validate(self) -> None:
        if self.starting_cash <= 0:
            raise ValueError("starting_cash must be positive")
        if not (0 < self.position_fraction <= 1):
            raise ValueError("position_fraction must be in (0, 1]")
        for name in ("fee_rate", "slippage"):
            if not (0 <= getattr(self, name) < 0.1):
                raise ValueError(f"{name} must be in [0, 0.1)")
        for name in ("stop_loss_pct", "take_profit_pct"):
            v = getattr(self, name)
            if v is not None and not (0 < v < 1):
                raise ValueError(f"{name} must be in (0, 1) or None")
        if not (0 < self.max_drawdown_pct <= 1):
            raise ValueError("max_drawdown_pct must be in (0, 1]")


@dataclass
class MarketConfig:
    coin_id: str = "bitcoin"
    vs_currency: str = "usd"

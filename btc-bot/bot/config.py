"""Default settings. Everything can be overridden on the command line."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StrategyConfig:
    fast: int = 9            # ma_cross: fast moving average length
    slow: int = 21           # ma_cross: slow moving average length
    kind: str = "sma"        # ma_cross: "sma" or "ema"
    name: str = "ma_cross"   # "ma_cross" or "supertrend"
    atr_period: int = 10     # supertrend: ATR length
    multiplier: float = 3.0  # supertrend: band width in ATRs

    def validate(self) -> None:
        if self.name == "supertrend":
            if self.atr_period < 1 or self.multiplier <= 0:
                raise ValueError("supertrend needs atr_period >= 1 and multiplier > 0")
            return
        if self.name != "ma_cross":
            raise ValueError(f"unknown strategy {self.name!r}")
        if self.kind not in ("sma", "ema"):
            raise ValueError(f"unknown moving average kind: {self.kind!r}")
        if not (1 <= self.fast < self.slow):
            raise ValueError(f"need 1 <= fast < slow, got fast={self.fast} slow={self.slow}")


@dataclass
class TrendConfig:
    """Higher-timeframe filter. Bullish = fast MA above slow MA on completed trend candles."""

    enabled: bool = False      # opt-in (--trend)
    interval: int = 3600       # 1h candles
    fast: int = 9
    slow: int = 21
    kind: str = "ema"
    allow_short: bool = False  # opt-in: open shorts on death crosses in a bearish trend

    def strategy(self) -> StrategyConfig:
        return StrategyConfig(name="ma_cross", fast=self.fast, slow=self.slow, kind=self.kind)

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
    stop_loss_pct: float | None = None      # optional: exit if price moves this much against the entry
    take_profit_pct: float | None = None    # optional fixed take-profit (both directions)
    max_drawdown_pct: float = 0.50    # kill switch: stop trading after -50 % from peak equity
                                      # (beyond the worst backtest drawdown of the default strategy)

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
    binance_symbol: str = "BTCUSDT"  # only used for history/warm-up candles

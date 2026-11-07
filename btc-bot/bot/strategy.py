"""Trading signals.

MACrossover  buy when the fast MA crosses above the slow MA, sell on the cross below (event signals)
Supertrend   ATR-band trend follower: "buy" while the trend is up, "sell" while it is down (state signals)

Every strategy has ``update(candle_or_close) -> "buy" | "sell" | None``, ``entry_reason``,
``exit_reason`` and ``lines()`` (indicator values for the dashboard).
"""

from __future__ import annotations

from collections import deque

from .config import StrategyConfig


class _SMA:
    def __init__(self, n: int) -> None:
        self.n = n
        self.window: deque[float] = deque(maxlen=n)
        self.total = 0.0

    def update(self, x: float) -> float | None:
        if len(self.window) == self.n:
            self.total -= self.window[0]
        self.window.append(x)
        self.total += x
        return self.total / self.n if len(self.window) == self.n else None


class _EMA:
    """EMA seeded with the SMA of the first n values."""

    def __init__(self, n: int) -> None:
        self.n = n
        self.alpha = 2.0 / (n + 1)
        self.seed: list[float] = []
        self.value: float | None = None

    def update(self, x: float) -> float | None:
        if self.value is None:
            self.seed.append(x)
            if len(self.seed) == self.n:
                self.value = sum(self.seed) / self.n
            return self.value
        self.value += self.alpha * (x - self.value)
        return self.value


class MACrossover:
    entry_reason = "golden_cross"
    exit_reason = "death_cross"

    def __init__(self, cfg: StrategyConfig) -> None:
        cfg.validate()
        self.cfg = cfg
        ma = _SMA if cfg.kind == "sma" else _EMA
        self._fast = ma(cfg.fast)
        self._slow = ma(cfg.slow)
        self.fast: float | None = None
        self.slow: float | None = None
        self._prev_diff: float | None = None

    @property
    def ready(self) -> bool:
        return self.fast is not None and self.slow is not None

    def lines(self) -> dict:
        return {"fast": self.fast, "slow": self.slow}

    def update(self, candle) -> str | None:
        """Feed one candle (or just its close). Returns "buy", "sell" or None."""
        close = getattr(candle, "close", candle)
        self.fast = self._fast.update(close)
        self.slow = self._slow.update(close)
        if not self.ready:
            return None
        diff = self.fast - self.slow
        prev, self._prev_diff = self._prev_diff, diff
        if prev is None:
            return None
        if prev <= 0 < diff:
            return "buy"
        if prev >= 0 > diff:
            return "sell"
        return None


class Supertrend:
    """Supertrend (ATR period n, multiplier m), Wilder ATR, standard band carry-over rules.

    Long while the close stays above the trailing lower band, flat once it closes below it.
    Returns a *state* signal on every candle once warmed up, so the engine enters as soon as
    the trend is up and the account is flat (also right after a restart).
    """

    entry_reason = "supertrend_up"
    exit_reason = "supertrend_down"

    def __init__(self, cfg: StrategyConfig) -> None:
        cfg.validate()
        self.cfg = cfg
        self.n, self.m = cfg.atr_period, cfg.multiplier
        self.atr: float | None = None
        self.prev_close: float | None = None
        self.upper: float | None = None   # final upper band
        self.lower: float | None = None   # final lower band
        self.direction = 1
        self.count = 0

    @property
    def ready(self) -> bool:
        return self.count > self.n

    @property
    def line(self) -> float | None:
        if self.upper is None:
            return None
        return self.lower if self.direction > 0 else self.upper

    def lines(self) -> dict:
        return {"fast": self.line if self.ready else None, "slow": None}

    def update(self, candle) -> str | None:
        h = getattr(candle, "high", None)
        lo = getattr(candle, "low", None)
        c = getattr(candle, "close", candle)
        if h is None or lo is None:
            h = lo = c
        pc = self.prev_close
        tr = h - lo if pc is None else max(h - lo, abs(h - pc), abs(lo - pc))
        self.atr = tr if self.atr is None else self.atr + (tr - self.atr) / self.n
        hl2 = (h + lo) / 2
        basic_up, basic_lo = hl2 + self.m * self.atr, hl2 - self.m * self.atr
        if self.upper is None:
            self.upper, self.lower = basic_up, basic_lo
        else:
            up, low = self.upper, self.lower  # previous final bands
            new_up = basic_up if basic_up < up or pc > up else up
            new_lo = basic_lo if basic_lo > low or pc < low else low
            if c > up:
                self.direction = 1
            elif c < low:
                self.direction = -1
            self.upper, self.lower = new_up, new_lo
        self.prev_close = c
        self.count += 1
        if not self.ready:
            return None
        return "buy" if self.direction > 0 else "sell"


def make_strategy(cfg: StrategyConfig):
    if cfg.name == "supertrend":
        return Supertrend(cfg)
    return MACrossover(cfg)

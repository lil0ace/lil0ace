"""Moving-average crossover: buy when the fast MA crosses above the slow MA, sell on the cross below."""

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

    def update(self, close: float) -> str | None:
        """Feed one candle close. Returns "buy", "sell" or None."""
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

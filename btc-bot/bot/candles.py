"""Turn price ticks into fixed-length candles."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Candle:
    start: int  # unix seconds, start of the interval
    open: float
    high: float
    low: float
    close: float

    def to_dict(self) -> dict:
        return {"t": self.start, "o": self.open, "h": self.high, "l": self.low, "c": self.close}


class CandleAggregator:
    """Collects ticks; returns candles once their interval is over.

    Intervals without ticks are filled with flat candles at the last close
    (at most ``max_gap_fill``), so time-based moving averages stay correct.
    """

    def __init__(self, seconds: int, max_gap_fill: int = 3600) -> None:
        if seconds < 1:
            raise ValueError("candle length must be >= 1 second")
        self.seconds = int(seconds)
        self.max_gap_fill = max_gap_fill
        self.current: Candle | None = None

    def _bucket(self, ts: float) -> int:
        return int(ts // self.seconds) * self.seconds

    def add(self, ts: float, price: float) -> list[Candle]:
        bucket = self._bucket(ts)
        cur = self.current
        if cur is None:
            self.current = Candle(bucket, price, price, price, price)
            return []
        if bucket < cur.start:  # late tick: fold into the current candle
            bucket = cur.start
        if bucket == cur.start:
            cur.high = max(cur.high, price)
            cur.low = min(cur.low, price)
            cur.close = price
            return []
        closed = [cur]
        gap = (bucket - cur.start) // self.seconds - 1
        for i in range(1, min(gap, self.max_gap_fill) + 1):
            c = cur.close
            closed.append(Candle(cur.start + i * self.seconds, c, c, c, c))
        self.current = Candle(bucket, price, price, price, price)
        return closed


def resample(points: list[tuple[float, float]], seconds: int) -> list[Candle]:
    """Group (timestamp, price) points into candles; the last, possibly unfinished one is included."""
    agg = CandleAggregator(seconds)
    out: list[Candle] = []
    for ts, price in sorted(points):
        out.extend(agg.add(ts, price))
    if agg.current is not None:
        out.append(agg.current)
    return out

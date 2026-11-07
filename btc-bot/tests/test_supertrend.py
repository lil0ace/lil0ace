import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from bot.candles import Candle
from bot.config import RiskConfig, StrategyConfig, TrendConfig
from bot.engine import TradingEngine
from bot.strategy import Supertrend

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "research"))
from strategy_tournament import supertrend_dir  # noqa: E402

ST = StrategyConfig(name="supertrend", atr_period=10, multiplier=3.0)


def random_candles(n=600, seed=1):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.02, n)))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) * (1 + rng.uniform(0, 0.01, n))
    low = np.minimum(open_, close) * (1 - rng.uniform(0, 0.01, n))
    return [Candle(i * 14400, o, h, lo, c) for i, (o, h, lo, c) in enumerate(zip(open_, high, low, close))]


def test_incremental_supertrend_matches_research_implementation():
    candles = random_candles()
    df = pd.DataFrame({"open": [c.open for c in candles], "high": [c.high for c in candles],
                       "low": [c.low for c in candles], "close": [c.close for c in candles]})
    expected = supertrend_dir(df, 10, 3.0).to_numpy()
    st = Supertrend(ST)
    signals = [st.update(c) for c in candles]
    assert signals[:10] == [None] * 10  # warm-up
    got = np.array([1 if s == "buy" else -1 for s in signals[10:]])
    assert (got == expected[10:]).all()


def test_engine_follows_supertrend_state():
    candles = random_candles()
    e = TradingEngine(ST, RiskConfig(max_drawdown_pct=1.0), trend_cfg=TrendConfig())
    for c in candles:
        e.on_candle(c)
    sides = [t.side for t in e.broker.trades]
    assert sides and all(a != b for a, b in zip(sides, sides[1:]))
    assert {t.reason for t in e.broker.trades} <= {"supertrend_up", "supertrend_down"}
    # in position exactly when the last signal says "buy"
    assert e.broker.in_position == (e.candles[-1]["signal"] == "buy")
    assert e.candles[-1]["fast"] is not None and e.candles[-1]["slow"] is None


def test_enters_after_restart_when_trend_already_up():
    up = [Candle(i * 14400, 100 + i, 101 + i, 99 + i, 100.5 + i) for i in range(30)]
    e = TradingEngine(ST, RiskConfig(), trend_cfg=TrendConfig())
    for c in up[:20]:
        e.warmup(c)          # e.g. history loaded at start-up
    trades = e.on_candle(up[20])
    assert [t.side for t in trades] == ["buy"]


@pytest.mark.parametrize("bad", [dict(atr_period=0), dict(multiplier=0)])
def test_invalid_supertrend_config(bad):
    with pytest.raises(ValueError):
        StrategyConfig(name="supertrend", **bad).validate()

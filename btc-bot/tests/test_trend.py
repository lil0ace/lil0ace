from bot.backtest import run_backtest
from bot.candles import Candle
from bot.config import RiskConfig, StrategyConfig, TrendConfig
from bot.engine import TradingEngine

TREND = TrendConfig(enabled=True, interval=4 * 3600, fast=2, slow=3, kind="sma", allow_short=True)
STRAT = StrategyConfig(fast=2, slow=4)
RISK = RiskConfig(stop_loss_pct=None, max_drawdown_pct=0.9)


def c(t, p):
    return Candle(t, p, p, p, p)


def engine_with_trend(prices_4h):
    e = TradingEngine(STRAT, RISK, trend_cfg=TREND)
    for i, p in enumerate(prices_4h):
        e.on_trend_candle(c(i * TREND.interval, p))
    return e


def feed(e, prices, t0=10**6):
    out = []
    for i, p in enumerate(prices):
        out += e.on_candle(c(t0 + i * 300, p))
    return out


# 5-min pattern: dip -> golden cross -> rally -> death cross -> fall -> golden cross
WAVE = [10, 9, 8, 7, 6, 8, 11, 14, 12, 9, 6, 4, 3, 5, 8, 11]


def test_bull_trend_longs_only_and_flattens_on_death_cross():
    e = engine_with_trend([100, 101, 102, 103])
    assert e.trend.state == "bull"
    trades = feed(e, WAVE)
    assert [(t.side, t.reason) for t in trades[:2]] == [("buy", "golden_cross"), ("sell", "death_cross")]
    assert all(t.side in ("buy", "sell") for t in trades)


def test_bear_trend_shorts_only_and_flattens_on_golden_cross():
    e = engine_with_trend([103, 102, 101, 100])
    assert e.trend.state == "bear"
    trades = feed(e, WAVE)
    assert [(t.side, t.reason) for t in trades] == [("short", "death_cross"), ("cover", "golden_cross")]
    assert trades[1].pnl > 0  # sold high, bought back lower


def test_no_short_option_stays_flat_in_bear_trend():
    e = TradingEngine(STRAT, RISK, trend_cfg=TrendConfig(enabled=True, interval=TREND.interval, fast=2, slow=3, kind="sma", allow_short=False))
    for i, p in enumerate([103, 102, 101, 100]):
        e.on_trend_candle(c(i * TREND.interval, p))
    assert feed(e, WAVE) == []


def test_no_entries_while_trend_unknown():
    e = engine_with_trend([100])  # not enough trend candles yet
    assert e.trend.state is None
    assert feed(e, WAVE) == []


def test_trend_flip_long_closed_by_death_cross_then_short_opened():
    e = engine_with_trend([100, 101, 102, 103])
    feed(e, WAVE[:8])                     # golden cross in bull -> long
    assert e.broker.is_long
    for i, p in enumerate([90, 80]):      # 4h trend turns bearish
        e.on_trend_candle(c((4 + i) * TREND.interval, p))
    assert e.trend.state == "bear"
    trades = feed(e, WAVE[8:12], t0=2 * 10**6)
    assert [t.side for t in trades] == ["sell", "short"]


def test_backtest_uses_only_closed_trend_candles():
    # trend candle starting at 0 closes at 14400; a 5-min candle ending before that must not see it
    trend = [c(-3 * 14400, 100), c(-2 * 14400, 101), c(-14400, 102), c(0, 50)]
    five = [c(14400 - 600 + i * 300, 100) for i in range(2)]  # ends at 14100 and 14400
    eng = run_backtest(five, STRAT, RISK, TREND, trend, interval=300)
    assert eng.candles[0]["trend"] == "bull"   # 4h candle at 0 not closed yet
    assert eng.candles[1]["trend"] == "bear"   # closes together with it: SMA2 76 < SMA3 84.3
    assert eng.trend.last_close_time == 14400


def test_default_rules_long_only_1h_and_death_cross_always_flattens():
    cfg = TrendConfig(enabled=True, fast=2, slow=3, kind="sma")  # defaults: 1h, no shorts
    assert cfg.interval == 3600 and not cfg.allow_short
    e = TradingEngine(STRAT, RiskConfig(max_drawdown_pct=0.9), trend_cfg=cfg)
    assert e.risk.stop_loss_pct is None
    for i, p in enumerate([100, 101, 102, 103]):
        e.on_trend_candle(c(i * 3600, p))
    feed(e, WAVE[:8])
    assert e.broker.is_long
    for i, p in enumerate([90, 80]):  # trend turns bearish while long
        e.on_trend_candle(c((4 + i) * 3600, p))
    trades = feed(e, WAVE[8:], t0=2 * 10**6)
    assert [(t.side, t.reason) for t in trades] == [("sell", "death_cross")]  # flattened, no short, no re-entry
    assert not e.broker.in_position

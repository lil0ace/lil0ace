import math

from bot.backtest import run_backtest, sweep
from bot.candles import Candle
from bot.config import RiskConfig, StrategyConfig
from bot.engine import TradingEngine


def candles_from(prices, step=60):
    return [Candle(i * step, p, p, p, p) for i, p in enumerate(prices)]


def wave(n=400):
    return [100 + 10 * math.sin(i / 15) for i in range(n)]


def test_backtest_trades_on_wave_and_metrics_consistent():
    eng = run_backtest(candles_from(wave()), StrategyConfig(5, 20), RiskConfig(stop_loss_pct=None))
    m = eng.metrics()
    assert m["round_trips"] >= 3
    assert m["equity"] == eng.broker.equity(eng.last_price)
    assert 0 <= m["max_drawdown_pct"] < 1
    sides = [t.side for t in eng.broker.trades]
    assert all(a != b for a, b in zip(sides, sides[1:]))  # strictly alternating buy/sell


def test_stop_loss_exits():
    prices = [100] * 25 + [101, 103, 106, 110] + [94]  # golden cross, then -7 % below entry
    eng = run_backtest(candles_from(prices), StrategyConfig(2, 5), RiskConfig(stop_loss_pct=0.05))
    reasons = [t.reason for t in eng.broker.trades]
    assert "golden_cross" in reasons and "stop_loss" in reasons


def test_kill_switch_halts_trading():
    prices = [100] * 10 + [105, 110] + [60] * 5 + [70, 80, 90, 100, 110]
    eng = run_backtest(candles_from(prices), StrategyConfig(2, 5),
                       RiskConfig(stop_loss_pct=None, max_drawdown_pct=0.2))
    assert eng.halted
    assert not eng.broker.in_position
    # the price recovers and crosses up again later, but no new entry is allowed once halted
    assert [t.reason for t in eng.broker.trades].count("golden_cross") == 1
    assert any(c["signal"] == "buy" for c in list(eng.candles)[-5:])


def test_account_snapshot_roundtrip():
    eng = run_backtest(candles_from(wave(200)), StrategyConfig(5, 20), RiskConfig())
    eng2 = TradingEngine(StrategyConfig(5, 20), RiskConfig())
    eng2.restore_account(eng.account_snapshot())
    assert eng2.broker.cash == eng.broker.cash
    assert len(eng2.broker.trades) == len(eng.broker.trades)


def test_sweep_skips_invalid_pairs():
    rows = sweep(candles_from(wave()), StrategyConfig(), RiskConfig(), [5, 30], [20, 30])
    assert {(r["fast"], r["slow"]) for r in rows} == {(5, 20), (5, 30)}

import pytest

from bot.config import StrategyConfig
from bot.strategy import MACrossover


def feed(strategy, prices):
    return [strategy.update(p) for p in prices]


def test_no_signal_before_warmup():
    s = MACrossover(StrategyConfig(fast=2, slow=4))
    assert feed(s, [1, 2, 3]) == [None, None, None]
    assert not s.ready


def test_golden_and_death_cross():
    s = MACrossover(StrategyConfig(fast=2, slow=4))
    # falling, then rising (golden cross), then falling again (death cross)
    signals = feed(s, [10, 9, 8, 7, 6, 8, 11, 14, 12, 9, 6, 4])
    assert "buy" in signals and "sell" in signals
    assert signals.index("buy") < signals.index("sell")
    assert signals.count("buy") == 1 and signals.count("sell") == 1


def test_sma_values():
    s = MACrossover(StrategyConfig(fast=2, slow=3))
    feed(s, [1, 2, 3])
    assert s.fast == pytest.approx(2.5)
    assert s.slow == pytest.approx(2.0)


def test_ema_seeded_with_sma():
    s = MACrossover(StrategyConfig(fast=2, slow=3, kind="ema"))
    feed(s, [1, 2, 3])
    assert s.slow == pytest.approx(2.0)          # seed = SMA(1,2,3)
    assert s.fast == pytest.approx(1.5 + 2 / 3 * (3 - 1.5))


@pytest.mark.parametrize("fast,slow,kind", [(5, 5, "sma"), (0, 3, "sma"), (2, 3, "wma")])
def test_invalid_config(fast, slow, kind):
    with pytest.raises(ValueError):
        MACrossover(StrategyConfig(fast=fast, slow=slow, kind=kind))

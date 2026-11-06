import pytest

from bot.broker import PaperBroker


def test_round_trip_with_fees_and_slippage():
    b = PaperBroker(starting_cash=10_000, fee_rate=0.001, slippage=0.0)
    buy = b.buy(100.0, 1)
    assert buy.qty == pytest.approx(99.9)
    assert b.cash == pytest.approx(0)
    sell = b.sell(110.0, 2)
    gross = 99.9 * 110
    assert b.cash == pytest.approx(gross * 0.999)
    assert sell.pnl == pytest.approx(gross * 0.999 - 10_000)
    assert not b.in_position


def test_slippage_worsens_fills():
    b = PaperBroker(starting_cash=1000, fee_rate=0.0, slippage=0.01)
    assert b.buy(100.0, 1).price == pytest.approx(101.0)
    assert b.sell(100.0, 2).price == pytest.approx(99.0)
    assert b.cash < 1000


def test_no_double_entry_or_empty_exit():
    b = PaperBroker()
    assert b.sell(100.0, 1) is None
    assert b.buy(100.0, 1) is not None
    assert b.buy(100.0, 2) is None


def test_serialisation_roundtrip():
    b = PaperBroker(starting_cash=500)
    b.buy(100.0, 1)
    b2 = PaperBroker.from_dict(b.to_dict())
    assert b2.qty == b.qty and b2.cash == b.cash and len(b2.trades) == 1

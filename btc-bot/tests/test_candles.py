from bot.candles import CandleAggregator, resample


def test_aggregates_ticks_into_candles():
    agg = CandleAggregator(60)
    assert agg.add(0, 10) == []
    assert agg.add(30, 12) == []
    assert agg.add(59, 9) == []
    closed = agg.add(61, 11)
    assert len(closed) == 1
    c = closed[0]
    assert (c.start, c.open, c.high, c.low, c.close) == (0, 10, 12, 9, 9)


def test_fills_gaps_with_flat_candles():
    agg = CandleAggregator(1)
    agg.add(0.2, 100)
    closed = agg.add(3.5, 105)
    assert [c.start for c in closed] == [0, 1, 2]
    assert all(c.close == 100 for c in closed)


def test_resample_sorts_and_keeps_last():
    candles = resample([(120, 3), (0, 1), (60, 2)], 60)
    assert [c.close for c in candles] == [1, 2, 3]

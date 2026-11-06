import pytest

from bot.binance import BinanceError, fetch_klines


class Resp:
    def __init__(self, status, payload):
        self.status_code, self._p, self.text = status, payload, str(payload)

    def json(self):
        return self._p


def row(open_s, price, interval=300):
    o = open_s * 1000
    return [o, str(price), str(price + 1), str(price - 1), str(price), "1", o + interval * 1000 - 1]


class Session:
    def __init__(self, pages):
        self.pages, self.params = list(pages), []

    def get(self, url, params=None, timeout=None):
        self.params.append(dict(params))
        return self.pages.pop(0) if self.pages else Resp(200, [])


def test_paginates_and_parses():
    first = [row(1_000_000 + i * 300, 100 + i) for i in range(1000)]
    second = [row(1_000_000 + (1000 + i) * 300, 200) for i in range(5)]
    s = Session([Resp(200, first), Resp(200, second), Resp(200, [])])
    candles = fetch_klines("btcusdt", 300, 1_000_000, 1_000_000 + 1005 * 300, session=s, sleep=lambda _: None)
    assert len(candles) == 1005
    assert candles[0].start == 1_000_000 and candles[0].close == 100 and candles[0].high == 101
    assert s.params[0]["symbol"] == "BTCUSDT" and s.params[0]["interval"] == "5m"
    assert s.params[1]["startTime"] == (1_000_000 + 1000 * 300) * 1000


def test_retries_on_rate_limit_then_fails_on_client_error():
    s = Session([Resp(429, {}), Resp(200, [row(1_000_000, 1)])])
    assert len(fetch_klines("BTCUSDT", 300, 1_000_000, 1_000_300, session=s, sleep=lambda _: None)) == 1
    with pytest.raises(BinanceError):
        fetch_klines("BTCUSDT", 300, 1_000_000, 1_000_300, session=Session([Resp(400, {"msg": "bad"})]))


def test_unknown_interval():
    with pytest.raises(ValueError):
        fetch_klines("BTCUSDT", 7, 0, 1)

import pytest

from bot.coingecko import CoinGeckoClient, CoinGeckoError, parse_ws_message


class FakeResp:
    def __init__(self, status, payload, headers=None):
        self.status_code, self._payload, self.headers, self.text = status, payload, headers or {}, str(payload)

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append((url, params, headers))
        return self.responses.pop(0)


def test_simple_price_and_demo_header():
    s = FakeSession([FakeResp(429, {}, {"retry-after": "1"}),
                     FakeResp(200, {"bitcoin": {"usd": 75000.5, "last_updated_at": 1700000000}})])
    c = CoinGeckoClient(api_key="k", plan="demo", session=s, sleep=lambda _: None)
    assert c.simple_price() == (75000.5, 1700000000.0)
    assert s.calls[-1][2]["x-cg-demo-api-key"] == "k"
    assert s.calls[-1][0].startswith("https://api.coingecko.com/")


def test_pro_plan_uses_pro_host():
    c = CoinGeckoClient(api_key="k", plan="pro", session=FakeSession([]))
    assert c.base_url.startswith("https://pro-api.coingecko.com")
    assert c.headers["x-cg-pro-api-key"] == "k"


def test_client_error_raises():
    c = CoinGeckoClient(api_key="", plan="public", session=FakeSession([FakeResp(401, {"error": "nope"})]))
    with pytest.raises(CoinGeckoError):
        c.market_chart()


def test_market_chart_converts_ms():
    s = FakeSession([FakeResp(200, {"prices": [[1700000000000, 1.0], [1700000060000, 2.0]]})])
    c = CoinGeckoClient(api_key="", plan="public", session=s)
    assert c.market_chart(days=1) == [(1700000000.0, 1.0), (1700000060.0, 2.0)]


def test_parse_ws_message():
    msg = {"c": "C1", "i": "bitcoin", "vs": "usd", "p": 75836.1, "t": 1794006360}
    assert parse_ws_message(msg, "bitcoin", "usd") == (1794006360.0, 75836.1)
    assert parse_ws_message({**msg, "t": 1794006360123}, "bitcoin", "usd")[0] == pytest.approx(1794006360.123)
    assert parse_ws_message({"message": msg}, "bitcoin", "usd") is not None
    assert parse_ws_message({"type": "ping"}, "bitcoin", "usd") is None
    assert parse_ws_message({**msg, "i": "ethereum"}, "bitcoin", "usd") is None

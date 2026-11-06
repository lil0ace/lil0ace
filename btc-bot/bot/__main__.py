"""Command line: python -m bot {backtest,paper,dashboard} ..."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from .backtest import fetch_history, run_backtest, sweep, write_trades_csv
from .coingecko import CoinGeckoClient
from .config import MarketConfig, RiskConfig, StrategyConfig
from .engine import TradingEngine
from .state import write_json

DATA_DIR = Path(os.getenv("BOT_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))


def _pct_or_none(v: str) -> float | None:
    f = float(v)
    return None if f <= 0 else f / 100.0


def _common(p: argparse.ArgumentParser) -> None:
    g = p.add_argument_group("strategy")
    g.add_argument("--fast", type=int, default=9, help="fast moving average length (candles)")
    g.add_argument("--slow", type=int, default=21, help="slow moving average length (candles)")
    g.add_argument("--ma", choices=["sma", "ema"], default="sma")
    r = p.add_argument_group("paper account & risk")
    r.add_argument("--cash", type=float, default=10_000.0, help="starting paper cash")
    r.add_argument("--fee", type=float, default=0.1, help="fee per fill in %%")
    r.add_argument("--slippage", type=float, default=0.05, help="slippage per fill in %%")
    r.add_argument("--fraction", type=float, default=100.0, help="%% of cash used per entry")
    r.add_argument("--stop-loss", type=_pct_or_none, default=0.03, help="stop loss in %% below entry (0 = off)")
    r.add_argument("--take-profit", type=_pct_or_none, default=None, help="take profit in %% above entry (0 = off)")
    r.add_argument("--max-drawdown", type=float, default=20.0, help="kill switch: halt after this %% drawdown")
    m = p.add_argument_group("market")
    m.add_argument("--coin", default="bitcoin", help="CoinGecko coin id")
    m.add_argument("--vs", default="usd", help="quote currency")


def _configs(a) -> tuple[StrategyConfig, RiskConfig, MarketConfig]:
    s = StrategyConfig(fast=a.fast, slow=a.slow, kind=a.ma)
    r = RiskConfig(
        starting_cash=a.cash, fee_rate=a.fee / 100, slippage=a.slippage / 100,
        position_fraction=a.fraction / 100, stop_loss_pct=a.stop_loss,
        take_profit_pct=a.take_profit, max_drawdown_pct=a.max_drawdown / 100,
    )
    s.validate()
    r.validate()
    return s, r, MarketConfig(coin_id=a.coin, vs_currency=a.vs)


def _fmt_pct(v) -> str:
    return "-" if v is None else f"{v * 100:+.2f}%"


def cmd_backtest(a) -> int:
    s, r, m = _configs(a)
    client = CoinGeckoClient()
    candles = fetch_history(client, m, a.days, a.interval)
    if len(candles) <= s.slow:
        print(f"only {len(candles)} candles - need more than slow={s.slow}. Use more --days or a shorter --interval.")
        return 1
    print(f"{len(candles)} candles of {a.interval}s for {m.coin_id}/{m.vs_currency} ({a.days} days)")

    if a.sweep:
        rows = sweep(candles, s, r, [5, 7, 9, 12, 15, 20], [21, 26, 30, 40, 50, 100])
        print(f"\n{'fast':>4} {'slow':>4} {'return':>9} {'buy&hold':>9} {'maxDD':>8} {'trades':>6} {'win%':>6}")
        for row in rows:
            wr = "-" if row["win_rate"] is None else f"{row['win_rate'] * 100:.0f}"
            print(f"{row['fast']:>4} {row['slow']:>4} {_fmt_pct(row['total_return_pct']):>9} "
                  f"{_fmt_pct(row['buy_hold_return_pct']):>9} {_fmt_pct(-row['max_drawdown_pct']):>8} "
                  f"{row['round_trips']:>6} {wr:>6}")
        print("\nTip: pick a region where neighbouring settings also do well, not the single best row (overfitting).")

    engine = run_backtest(candles, s, r)
    mt = engine.metrics()
    print(f"\nMA crossover {s.kind.upper()} {s.fast}/{s.slow}")
    print(f"  start equity   {r.starting_cash:,.2f}")
    print(f"  end equity     {mt['equity']:,.2f}  ({_fmt_pct(mt['total_return_pct'])})")
    print(f"  buy & hold     {_fmt_pct(mt['buy_hold_return_pct'])}")
    print(f"  max drawdown   {_fmt_pct(-mt['max_drawdown_pct'])}")
    print(f"  round trips    {mt['round_trips']}  win rate {'-' if mt['win_rate'] is None else format(mt['win_rate'] * 100, '.0f') + '%'}")
    print(f"  fees paid      {mt['total_fees']:,.2f}")
    if engine.broker.in_position:
        print(f"  open position  {engine.broker.qty:.6f} @ {engine.broker.entry_price:,.2f} (marked to market)")
    if mt["halted"]:
        print(f"  KILL SWITCH    {mt['halt_reason']}")

    state_path = DATA_DIR / "backtest_state.json"
    write_json(state_path, engine.to_state(mode="backtest", coin=m.coin_id, vs=m.vs_currency,
                                           candle_seconds=a.interval, days=a.days, status="finished"))
    write_trades_csv(engine, DATA_DIR / "backtest_trades.csv")
    print(f"\nsaved {state_path} and backtest_trades.csv")
    if a.dashboard:
        from .dashboard import serve
        print(f"dashboard: http://{a.host}:{a.port}/?state=backtest  (Ctrl+C to stop)")
        serve(DATA_DIR, a.host, a.port)
    return 0


def cmd_paper(a) -> int:
    from .live import PaperTrader, run_rest, run_ws

    s, r, m = _configs(a)
    client = CoinGeckoClient()
    candle_seconds = a.candle_seconds or (1 if a.source == "ws" else 60)
    if a.source == "rest" and candle_seconds < a.poll:
        print(f"warning: candles ({candle_seconds}s) shorter than poll interval ({a.poll}s) -> many flat candles")
    engine = TradingEngine(s, r)
    name = a.name
    trader = PaperTrader(engine, candle_seconds, m, DATA_DIR / f"{name}_state.json",
                         DATA_DIR / f"{name}_account.json", a.source)
    if a.reset:
        (DATA_DIR / f"{name}_account.json").unlink(missing_ok=True)
    elif trader.load_account():
        print("resumed existing paper account (use --reset to start over)")
    try:
        trader.warmup(client)
    except Exception as exc:  # warm-up is optional
        logging.warning("warm-up skipped: %s", exc)

    if a.dashboard:
        from .dashboard import serve
        serve(DATA_DIR, a.host, a.port, background=True)
        print(f"dashboard: http://{a.host}:{a.port}/?state={name}")

    print(f"paper trading {m.coin_id}/{m.vs_currency} via {a.source}, {candle_seconds}s candles, "
          f"{s.kind.upper()} {s.fast}/{s.slow}. Simulated only - no real orders. Ctrl+C to stop.")
    if a.source == "ws":
        key = os.getenv("COINGECKO_API_KEY")
        if not key:
            print("the WebSocket stream needs COINGECKO_API_KEY from a paid CoinGecko plan; "
                  "use --source rest for the free API")
            return 2
        run_ws(trader, key)
    else:
        run_rest(trader, client, a.poll)
    return 0


def cmd_dashboard(a) -> int:
    from .dashboard import serve
    print(f"dashboard: http://{a.host}:{a.port}/  (Ctrl+C to stop)")
    serve(DATA_DIR, a.host, a.port)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m bot", description="BTC moving-average crossover paper trading bot")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("backtest", help="test the strategy on CoinGecko history")
    _common(b)
    b.add_argument("--days", type=float, default=7, help="history length (1 day = 5-min data, 2-90 = hourly)")
    b.add_argument("--interval", type=int, default=3600, help="candle length in seconds")
    b.add_argument("--sweep", action="store_true", help="also test a grid of fast/slow settings")
    b.add_argument("--dashboard", action="store_true", help="open the dashboard afterwards")

    pp = sub.add_parser("paper", help="forward test on live prices (paper money)")
    _common(pp)
    pp.add_argument("--source", choices=["rest", "ws"], default="rest")
    pp.add_argument("--candle-seconds", type=int, default=None, help="default: 60 (rest) / 1 (ws)")
    pp.add_argument("--poll", type=float, default=30.0, help="REST poll interval in seconds")
    pp.add_argument("--name", default="paper", help="name for state/account files")
    pp.add_argument("--reset", action="store_true", help="discard the saved paper account")
    pp.add_argument("--dashboard", action="store_true", help="serve the dashboard alongside")

    d = sub.add_parser("dashboard", help="serve the dashboard only")
    for sp in (b, pp, d):
        sp.add_argument("--host", default=os.getenv("DASHBOARD_HOST", "127.0.0.1"))
        sp.add_argument("--port", type=int, default=int(os.getenv("DASHBOARD_PORT", "8000")))

    a = p.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        return {"backtest": cmd_backtest, "paper": cmd_paper, "dashboard": cmd_dashboard}[a.cmd](a)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

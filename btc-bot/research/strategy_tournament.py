"""Compare popular BTC strategies on Binance BTCUSDT history (long only, spot).

Usage:
    python research/strategy_tournament.py data/btcusdt_1h.csv

Conventions (identical for every strategy):
  * signals are computed on a candle's close and held from the next candle on (no look-ahead)
  * cost per position change: 0.1 % fee + 0.05 % slippage = 0.15 % of the traded amount
  * standard textbook parameters, nothing optimised on this data
  * long or flat only (no shorts, no leverage)
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

COST = 0.0015
START = "2018-01-01"
SPLIT = "2022-01-01"  # in-sample 2018-2021, out-of-sample 2022-today


# ---------------------------------------------------------------- data
def load(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.index = pd.to_datetime(df.pop("t"), unit="s", utc=True)
    return df.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close"})


def resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    out = df.resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"})
    return out.dropna()


# ---------------------------------------------------------------- indicators
def sma(s, n): return s.rolling(n).mean()
def ema(s, n): return s.ewm(span=n, adjust=False).mean()


def rsi(s, n):
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def atr(df, n):
    pc = df.close.shift()
    tr = pd.concat([df.high - df.low, (df.high - pc).abs(), (df.low - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def adx(df, n=14):
    up, dn = df.high.diff(), -df.low.diff()
    plus = np.where((up > dn) & (up > 0), up, 0.0)
    minus = np.where((dn > up) & (dn > 0), dn, 0.0)
    a = atr(df, n)
    pdi = 100 * pd.Series(plus, df.index).ewm(alpha=1 / n, adjust=False).mean() / a
    mdi = 100 * pd.Series(minus, df.index).ewm(alpha=1 / n, adjust=False).mean() / a
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi)
    return dx.ewm(alpha=1 / n, adjust=False).mean()


def supertrend_dir(df, n=10, mult=3.0):
    a = atr(df, n).to_numpy()
    hl2 = ((df.high + df.low) / 2).to_numpy()
    close = df.close.to_numpy()
    upper, lower = hl2 + mult * a, hl2 - mult * a
    fu, fl = upper.copy(), lower.copy()
    direction = np.ones(len(df))
    for i in range(1, len(df)):
        fu[i] = upper[i] if upper[i] < fu[i - 1] or close[i - 1] > fu[i - 1] else fu[i - 1]
        fl[i] = lower[i] if lower[i] > fl[i - 1] or close[i - 1] < fl[i - 1] else fl[i - 1]
        if close[i] > fu[i - 1]:
            direction[i] = 1
        elif close[i] < fl[i - 1]:
            direction[i] = -1
        else:
            direction[i] = direction[i - 1]
    return pd.Series(direction, df.index)


def state_machine(enter: pd.Series, exit_: pd.Series) -> pd.Series:
    """1 after an entry signal until an exit signal."""
    e, x = enter.fillna(False).to_numpy(), exit_.fillna(False).to_numpy()
    pos = np.zeros(len(e))
    cur = 0.0
    for i in range(len(e)):
        if cur == 0 and e[i]:
            cur = 1.0
        elif cur == 1 and x[i]:
            cur = 0.0
        pos[i] = cur
    return pd.Series(pos, enter.index)


# ---------------------------------------------------------------- strategies
# each returns (timeframe dataframe, position series decided on each candle's close)
def strategies(h1: pd.DataFrame) -> dict:
    d1, h4 = resample(h1, "1D"), resample(h1, "4h")
    c, c4, ch = d1.close, h4.close, h1.close
    S = {}
    S["Buy & Hold"] = (d1, pd.Series(1.0, d1.index))
    S["Kurs > SMA 200 (1D)"] = (d1, (c > sma(c, 200)).astype(float))
    S["Golden Cross SMA 50/200 (1D)"] = (d1, (sma(c, 50) > sma(c, 200)).astype(float))
    S["SMA 21/50 Cross (4h)"] = (h4, (sma(c4, 21) > sma(c4, 50)).astype(float))
    S["SMA 9/21 Cross (1h)"] = (h1, (sma(ch, 9) > sma(ch, 21)).astype(float))
    S["EMA 9/21 Cross (1D)"] = (d1, (ema(c, 9) > ema(c, 21)).astype(float))
    S["EMA 20/50 Cross (1D)"] = (d1, (ema(c, 20) > ema(c, 50)).astype(float))
    S["Donchian 20/10 Turtle (1D)"] = (d1, state_machine(c > d1.high.rolling(20).max().shift(),
                                                        c < d1.low.rolling(10).min().shift()))
    S["Donchian 55/20 Turtle (1D)"] = (d1, state_machine(c > d1.high.rolling(55).max().shift(),
                                                        c < d1.low.rolling(20).min().shift()))
    S["Donchian 20/10 + ADX>25 (1D)"] = (d1, state_machine((c > d1.high.rolling(20).max().shift()) & (adx(d1) > 25),
                                                          c < d1.low.rolling(10).min().shift()))
    S["Momentum 30 Tage (1D)"] = (d1, (c > c.shift(30)).astype(float))
    S["Momentum 90 Tage (1D)"] = (d1, (c > c.shift(90)).astype(float))
    m, sig = ema(c, 12) - ema(c, 26), None
    S["MACD 12/26/9 (1D)"] = (d1, (m > ema(m, 9)).astype(float))
    m4 = ema(c4, 12) - ema(c4, 26)
    S["MACD 12/26/9 (4h)"] = (h4, (m4 > ema(m4, 9)).astype(float))
    S["Supertrend 10/3 (1D)"] = (d1, (supertrend_dir(d1) > 0).astype(float))
    S["Supertrend 10/3 (4h)"] = (h4, (supertrend_dir(h4) > 0).astype(float))
    r = rsi(c, 14)
    S["RSI 14 30/70 Mean Rev. (1D)"] = (d1, state_machine(r < 30, r > 70))
    S["Connors RSI-2 (1D)"] = (d1, state_machine((rsi(c, 2) < 10) & (c > sma(c, 200)), c > sma(c, 5)))
    mid, sd = sma(c, 20), c.rolling(20).std()
    S["Bollinger Mean Rev. 20/2 (1D)"] = (d1, state_machine(c < mid - 2 * sd, c > mid))
    S["Bollinger Breakout 20/2 (1D)"] = (d1, state_machine(c > mid + 2 * sd, c < mid))
    # Quantpedia: hold BTC 21:00-23:00 UTC every day (decided on the 20:00 and 21:00 candle closes)
    hours = ch.index.hour
    S["Saisonalität 21-23 UTC (1h)"] = (h1, pd.Series(np.isin(hours, [20, 21]).astype(float), ch.index))
    up = (c > sma(c, 20)).shift().reindex(ch.index, method="ffill").fillna(False)  # yesterday's daily trend
    S["Saisonalität 21-23 UTC + Aufwärtstrend (1h)"] = (h1, (np.isin(hours, [20, 21]) & up).astype(float))
    return S


# ---------------------------------------------------------------- evaluation
def equity_curve(df: pd.DataFrame, pos: pd.Series, start, end=None) -> tuple[pd.Series, int, float]:
    df, pos = df.loc[start:end], pos.reindex(df.index).loc[start:end].fillna(0)
    held = pos.shift().fillna(0)                      # decided at previous close
    ret = df.close.pct_change().fillna(0)
    trades = held.diff().abs().fillna(held.iloc[0])
    net = held * ret - trades * COST
    eq = (1 + net).cumprod()
    return eq, int((trades > 0).sum() // 2 + (held.iloc[-1] > 0)), float(held.mean())


def stats(eq: pd.Series) -> dict:
    daily = eq.resample("1D").last().dropna()
    rets = daily.pct_change().dropna()
    years = (daily.index[-1] - daily.index[0]).days / 365.25
    cagr = daily.iloc[-1] ** (1 / years) - 1 if years > 0 else 0
    dd = (daily / daily.cummax() - 1).min()
    sharpe = rets.mean() / rets.std() * np.sqrt(365) if rets.std() > 0 else 0
    return {"cagr": cagr, "maxdd": dd, "sharpe": sharpe, "calmar": cagr / -dd if dd < 0 else 0,
            "total": daily.iloc[-1] - 1}


def main(path: str) -> None:
    h1 = load(path)
    S = strategies(h1)
    rows = []
    for name, (df, pos) in S.items():
        eq, trades, exposure = equity_curve(df, pos, START)
        full = stats(eq)
        ins = stats(equity_curve(df, pos, START, "2021-12-31")[0])
        oos = stats(equity_curve(df, pos, SPLIT)[0])
        years = {y: stats(equity_curve(df, pos, f"{y}-01-01", f"{y}-12-31")[0])["total"]
                 for y in range(2018, pd.Timestamp.now().year + 1)}
        rows.append({"name": name, **full, "trades": trades, "exposure": exposure,
                     "is_cagr": ins["cagr"], "is_calmar": ins["calmar"],
                     "oos_cagr": oos["cagr"], "oos_calmar": oos["calmar"], "oos_maxdd": oos["maxdd"],
                     "oos_sharpe": oos["sharpe"], **{str(y): v for y, v in years.items()}})
    res = pd.DataFrame(rows).set_index("name")
    bh = res.loc["Buy & Hold"]
    res["passes"] = (res.is_cagr > 0) & (res.oos_cagr > 0) & (res.is_calmar > bh.is_calmar) & (res.oos_calmar > bh.oos_calmar)
    res = res.sort_values("calmar", ascending=False)

    pct = lambda v: f"{v * 100:+.0f}%"
    print(f"BTCUSDT {START} bis {h1.index[-1]:%Y-%m-%d}, Kosten {COST * 100:.2f}% pro Positionswechsel\n")
    print(f"{'Strategie':44s} {'CAGR':>6} {'MaxDD':>6} {'Sharpe':>6} {'Calmar':>6} {'Trades':>6} {'Invest':>6} | "
          f"{'IS CAGR':>7} {'OOS CAGR':>8} {'OOS DD':>7} {'OOS Calm':>8} | ok")
    for n, r in res.iterrows():
        print(f"{n:44s} {pct(r.cagr):>6} {pct(r.maxdd):>6} {r.sharpe:6.2f} {r.calmar:6.2f} {int(r.trades):6d} {r.exposure * 100:5.0f}% | "
              f"{pct(r.is_cagr):>7} {pct(r.oos_cagr):>8} {pct(r.oos_maxdd):>7} {r.oos_calmar:8.2f} | {'JA' if r.passes else '-'}")
    print("\nJahresrenditen:")
    ycols = [c for c in res.columns if c.isdigit()]
    print(f"{'Strategie':44s} " + " ".join(f"{y:>6}" for y in ycols))
    for n, r in res.iterrows():
        print(f"{n:44s} " + " ".join(f"{pct(r[y]):>6}" for y in ycols))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data/btcusdt_1h.csv")

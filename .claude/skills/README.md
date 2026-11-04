# Installierte Claude-Code-Skills für den BTC-Tradingbot

Projekt-Skills: Claude Code lädt sie automatisch, wenn es in diesem Repo arbeitet.
Kopiert (unverändert, MIT-Lizenz) aus:

- [tradermonty/claude-trading-skills](https://github.com/tradermonty/claude-trading-skills) @ d8e71ce
- [agiprolabs/claude-trading-skills](https://github.com/agiprolabs/claude-trading-skills) @ 981e1d7

| Skill | Quelle | Wofür |
|---|---|---|
| crypto-regime-analyzer | tradermonty | Krypto-Marktlage 0–100 (Risk-on/off, BTC-Dominanz, Funding) – ohne API-Key |
| technical-analyst | tradermonty | Chart-/Technische Analyse |
| backtest-expert | tradermonty | Backtests kritisch bewerten (Overfitting, Robustheit) |
| edge-strategy-reviewer | tradermonty | Strategie-Entwürfe prüfen |
| position-sizer | tradermonty | Positionsgröße aus Risiko/Stop berechnen |
| drawdown-circuit-breaker | tradermonty | Not-Aus/Handelspause bei Drawdown |
| pre-trade-discipline-gate | tradermonty | Checkliste vor jedem Trade |
| trader-memory-core | tradermonty | Trade-Gedächtnis / Thesen-Tracking |
| strategy-framework | agiprolabs | Struktur für Strategie-Code |
| ohlcv-processing | agiprolabs | Kerzendaten laden/bereinigen/resamplen |
| pandas-ta | agiprolabs | Indikatoren mit pandas-ta |
| vectorbt | agiprolabs | Schnelle vektorisierte Backtests |
| walk-forward-validation | agiprolabs | Out-of-Sample-Validierung |
| regime-detection | agiprolabs | Marktregime erkennen |
| volatility-modeling | agiprolabs | Volatilität (ATR, GARCH …) |
| risk-management | agiprolabs | Risiko-Limits, Portfolio-Risiko |
| position-sizing / kelly-criterion | agiprolabs | Positionsgrößen-Methoden |
| exit-strategies | agiprolabs | Stops, Take-Profit, Trailing |
| slippage-modeling | agiprolabs | Gebühren/Slippage realistisch modellieren |
| trade-journal | agiprolabs | Trading-Journal führen |

Hinweis: Einige tradermonty-Skills sind auf Aktien ausgelegt; Skripte, die `FMP_API_KEY`
(financialmodelingprep.com) brauchen, sind für BTC nicht nötig.

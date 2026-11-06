# BTC Paper-Trading-Bot (Moving-Average-Crossover)

Nachbau des Ablaufs aus dem Video „Crypto Trading Bot with AI: The $10K Challenge“:

1. **Strategie:** Moving-Average-Crossover. Kauf, wenn der schnelle MA den langsamen nach oben kreuzt („Golden Cross“); Verkauf beim Kreuzen nach unten („Death Cross“).
2. **Dashboard** mit Paper-Equity, Preis-Chart, MAs, Kauf/Verkauf-Markern und Trade-Liste.
3. **Live-Preise** über die CoinGecko-API.
4. **Backtest** auf historischen CoinGecko-Daten.
5. **Forward-Test** live: per REST (kostenlos) oder per CoinGecko-WebSocket mit Ticks unter einer Sekunde und 1-Sekunden-Kerzen.

> ⚠️ **Nur Papiergeld.** Der Bot sendet keine echten Orders und hat keinen Börsenzugang. Alle Ergebnisse sind simuliert. Keine Anlageberatung.

![Dashboard](docs/dashboard.png)

## Schnellstart

```bash
cd btc-bot
pip install -r requirements.txt

# Backtest: 7 Tage, 1-Stunden-Kerzen, SMA 9/21
python -m bot backtest --days 7 --interval 3600

# Backtest mit Parameter-Raster und Dashboard danach
python -m bot backtest --days 30 --interval 3600 --sweep --dashboard

# Forward-Test mit Live-Preisen (REST, kostenlos) und Dashboard auf http://127.0.0.1:8000
python -m bot paper --candle-seconds 300 --poll 30 --dashboard

# Forward-Test über WebSocket mit 1-Sekunden-Kerzen (braucht einen bezahlten CoinGecko-Key)
export COINGECKO_API_KEY=...  COINGECKO_PLAN=pro
python -m bot paper --source ws --fast 9 --slow 21 --dashboard
```

Nur das Dashboard starten: `python -m bot dashboard`. Oben rechts lässt sich zwischen `backtest` und `paper` umschalten.

## Wichtige Optionen

| Option | Standard | Bedeutung |
|---|---|---|
| `--fast` / `--slow` | 9 / 21 | Länge der MAs in Kerzen |
| `--ma` | `sma` | `sma` oder `ema` |
| `--cash` | 10000 | Start-Kapital (Papier) |
| `--fee` / `--slippage` | 0.1 / 0.05 | Gebühr und Slippage pro Ausführung in % |
| `--stop-loss` | 3 | Stop-Loss in % unter Einstieg (`0` = aus) |
| `--take-profit` | aus | Take-Profit in % über Einstieg |
| `--max-drawdown` | 20 | Not-Aus: Bei diesem Verlust vom Höchststand wird verkauft und der Handel gestoppt |
| `--fraction` | 100 | Anteil des Cash pro Einstieg in % |
| `--days` / `--interval` | 7 / 3600 | Backtest-Zeitraum und Kerzenlänge in Sekunden |
| `--source` | `rest` | `rest` (kostenlos) oder `ws` (WebSocket, bezahlt) |
| `--candle-seconds` | 60 (rest) / 1 (ws) | Kerzenlänge im Forward-Test |
| `--reset` | – | gespeichertes Paper-Konto verwerfen |

CoinGecko-Granularität: `--days 1` liefert ~5-Minuten-Daten, 2–90 Tage stündliche, mehr als 90 Tage tägliche Daten.
Die öffentliche API ist stark limitiert. Mit `--poll` unter ~15 s kommen schnell HTTP-429-Antworten; der Bot wartet dann automatisch und versucht es erneut.
Ein kostenloser **Demo-Key** (`COINGECKO_PLAN=demo`) erhöht das Limit.
Die REST-Preise aktualisiert CoinGecko nur etwa alle 20–60 s. Für kurze Kerzen ist deshalb die WebSocket-Quelle gedacht.

## Dauerbetrieb (Docker)

```bash
cp .env.example .env      # optional: Key eintragen
docker compose up -d --build
docker compose logs -f
```

- `restart: unless-stopped` startet den Bot nach einem Absturz oder Reboot neu.
- Das Paper-Konto liegt in `data/paper_account.json` und wird nach jedem Trade gespeichert. Nach einem Neustart macht der Bot dort weiter.
- Der Healthcheck markiert den Container als `unhealthy`, wenn der Status länger als 5 Minuten nicht aktualisiert wurde.
- Das Dashboard ist nur lokal erreichbar (`127.0.0.1:8000`). Für Zugriff von außen einen SSH-Tunnel nutzen, den Port nicht offen ins Internet stellen.

## Aufbau

```
bot/
  coingecko.py  REST-Client (Retry/Backoff bei 429) + WebSocket-Stream
  candles.py    Ticks → Kerzen (füllt Lücken mit flachen Kerzen)
  strategy.py   SMA/EMA-Crossover-Signale
  broker.py     Paper-Konto: Gebühren, Slippage, Trade-Log
  engine.py     Strategie + Risiko-Regeln + Konto, identisch für Backtest und Live
  backtest.py   Backtest, Parameter-Raster, CSV-Export
  live.py       Forward-Test (REST-Polling oder WebSocket mit Reconnect)
  dashboard.py  kleiner Webserver (nur Standardbibliothek)
dashboard/index.html  Dashboard (Chart.js)
tests/        pytest-Tests (python -m pytest)
```

Backtest und Forward-Test nutzen dieselbe `TradingEngine`. Live-Ergebnisse sind dadurch direkt mit dem Backtest vergleichbar.

## Ehrliche Einordnung

Ein einfacher MA-Crossover ist in Seitwärtsphasen anfällig für viele Fehlsignale, und Gebühren fressen die Gewinne. Im Test über 30 Tage (Okt./Nov. 2026, 1h-Kerzen, SMA 9/21) lag der Bot bei **−14 %**, Buy & Hold bei **−9 %**.
Bevor echtes Geld ins Spiel kommt:

- Mit `--sweep` prüfen, ob auch *benachbarte* Einstellungen funktionieren, nicht nur die beste Zeile (sonst Overfitting).
- Mehrere Zeiträume testen (Bullen-, Bären-, Seitwärtsmarkt).
- Wochenlang im Forward-Test laufen lassen und mit dem Backtest vergleichen.
- Die installierten Claude-Skills `backtest-expert`, `walk-forward-validation` und `risk-management` helfen dabei.

# BTC Paper-Trading-Bot (Moving-Average-Crossover)

Nachbau des Ablaufs aus dem Video „Crypto Trading Bot with AI: The $10K Challenge“, erweitert um einen 1h-Trendfilter:

1. **Strategie:** Moving-Average-Crossover im **5-Minuten-Chart**, gefiltert durch den **1h-Trend** (siehe unten).
2. **Dashboard** mit Paper-Equity, Preis-Chart, MAs, Kauf/Verkauf-Markern und Trade-Liste.
3. **Live-Preise** über die CoinGecko-API.
4. **Backtest** auf historischen CoinGecko-Daten.
5. **Forward-Test** live: per REST (kostenlos) oder per CoinGecko-WebSocket mit Ticks unter einer Sekunde und 1-Sekunden-Kerzen.

> ⚠️ **Nur Papiergeld.** Der Bot sendet keine echten Orders und hat keinen Börsenzugang. Alle Ergebnisse sind simuliert. Keine Anlageberatung.

![Dashboard](docs/dashboard.png)

## Handelsregeln

Der Bot macht genau zwei Dinge:

1. **Kaufen:** 5-min Golden Cross (SMA 9 kreuzt SMA 21 nach oben), **aber nur, wenn der 1h-Trend bullisch ist**.
2. **Glattstellen:** 5-min Death Cross (SMA 9 kreuzt SMA 21 nach unten). Das gilt immer, egal wie der 1h-Trend gerade steht.

Sonst nichts: keine Shorts, kein Stop-Loss, kein Take-Profit, keine Käufe bei bärischem oder noch unbekanntem Trend.

- Der 1h-Trend gilt als **bullisch**, wenn auf abgeschlossenen 1h-Kerzen der EMA 9 über dem EMA 21 liegt.
- Der Backtest nutzt eine 1h-Kerze erst ab ihrem Schlusszeitpunkt. Er schaut also nicht in die Zukunft.
- Einzige Absicherung ist der Not-Aus bei 20 % Verlust vom Höchststand (`--max-drawdown`). Mit `--max-drawdown 100` ist er aus.
- Optional, standardmäßig aus: `--stop-loss 3`, `--take-profit 5`, `--allow-short` (Death Cross im bärischen Trend eröffnet einen Short, der nächste Golden Cross schließt ihn), `--trend-interval 14400` (4h statt 1h), `--no-trend` (jeder Golden Cross wird gekauft).

## Schnellstart

```bash
cd btc-bot
pip install -r requirements.txt

# Backtest: letzte 24 h in 5-min-Kerzen mit 1h-Trendfilter
python -m bot backtest

# dasselbe mit Parameter-Raster und Dashboard danach
python -m bot backtest --sweep --dashboard

# Forward-Test mit Live-Preisen (REST, kostenlos) und Dashboard auf http://127.0.0.1:8000
python -m bot paper --dashboard

# Forward-Test über WebSocket (Ticks unter einer Sekunde, braucht einen bezahlten CoinGecko-Key)
export COINGECKO_API_KEY=...  COINGECKO_PLAN=pro
python -m bot paper --source ws --dashboard

# ohne Trendfilter auf 1h-Kerzen über 30 Tage (alte Variante)
python -m bot backtest --no-trend --days 30 --interval 3600
```

Nur das Dashboard starten: `python -m bot dashboard`. Oben rechts lässt sich zwischen `backtest` und `paper` umschalten.

## Wichtige Optionen

| Option | Standard | Bedeutung |
|---|---|---|
| `--fast` / `--slow` | 9 / 21 | Länge der MAs in Kerzen |
| `--ma` | `sma` | `sma` oder `ema` (5-min-Signal) |
| `--trend-interval` | 3600 | Trend-Zeitrahmen in Sekunden (3600 = 1h, 14400 = 4h) |
| `--trend-fast` / `--trend-slow` / `--trend-ma` | 9 / 21 / `ema` | MAs für die Trendbestimmung |
| `--allow-short` | aus | auch Shorts im bärischen Trend |
| `--no-trend` | – | Trendfilter aus: jeder Golden Cross wird gekauft |
| `--cash` | 10000 | Start-Kapital (Papier) |
| `--fee` / `--slippage` | 0.1 / 0.05 | Gebühr und Slippage pro Ausführung in % |
| `--stop-loss` | aus | optionaler Stop-Loss in % |
| `--take-profit` | aus | Take-Profit in % |
| `--max-drawdown` | 20 | Not-Aus: Bei diesem Verlust vom Höchststand wird verkauft und der Handel gestoppt |
| `--fraction` | 100 | Anteil des Cash pro Einstieg in % |
| `--days` / `--interval` | 1 / 300 | Backtest-Zeitraum und Kerzenlänge in Sekunden |
| `--source` | `rest` | `rest` (kostenlos) oder `ws` (WebSocket, bezahlt) |
| `--candle-seconds` | 300 | Signal-Kerzenlänge im Forward-Test |
| `--reset` | – | gespeichertes Paper-Konto verwerfen |

CoinGecko-Granularität: `--days 1` liefert ~5-Minuten-Daten, 2–90 Tage stündliche, mehr als 90 Tage tägliche Daten.
**5-Minuten-Backtests gehen mit der kostenlosen API deshalb nur über die letzten 24 Stunden.** Für die 1h-Trendkerzen lädt der Bot automatisch stündliche Daten der letzten Tage nach.
Ein Tag ist eine sehr kleine Stichprobe. Aussagekräftiger ist der Forward-Test über mehrere Wochen.
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
  broker.py     Paper-Konto (Long, optional Short): Gebühren, Slippage, Trade-Log
  engine.py     5-min-Signale + 1h-Trendfilter + Konto, identisch für Backtest und Live
  backtest.py   Backtest, Parameter-Raster, CSV-Export
  live.py       Forward-Test (REST-Polling oder WebSocket mit Reconnect)
  dashboard.py  kleiner Webserver (nur Standardbibliothek)
dashboard/index.html  Dashboard (Chart.js)
tests/        pytest-Tests (python -m pytest)
```

Backtest und Forward-Test nutzen dieselbe `TradingEngine`. Live-Ergebnisse sind dadurch direkt mit dem Backtest vergleichbar.

## Ehrliche Einordnung

Ein einfacher MA-Crossover ist in Seitwärtsphasen anfällig für viele Fehlsignale, und Gebühren fressen die Gewinne.
- Ohne Trendfilter, 30 Tage (Okt./Nov. 2026, 1h-Kerzen, SMA 9/21): **−14 %**, Buy & Hold **−9 %**.
- Mit 4h-Trendfilter und Shorts, 5-min-Kerzen, letzte 24 h (06.11.2026): **−4 %** bei 7 Trades (0 Gewinner), Buy & Hold **+0,1 %**.
- Aktuelle Regeln (1h-Trend, nur Long), dieselben 24 h: **0 Trades, ±0 %**. Der 1h-Trend war den ganzen Tag bärisch, alle 8 Golden Crosses wurden gefiltert.
Bevor echtes Geld ins Spiel kommt:

- Mit `--sweep` prüfen, ob auch *benachbarte* Einstellungen funktionieren, nicht nur die beste Zeile (sonst Overfitting).
- Mehrere Zeiträume testen (Bullen-, Bären-, Seitwärtsmarkt).
- Wochenlang im Forward-Test laufen lassen und mit dem Backtest vergleichen.
- Die installierten Claude-Skills `backtest-expert`, `walk-forward-validation` und `risk-management` helfen dabei.

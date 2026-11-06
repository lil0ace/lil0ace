# BTC Paper-Trading-Bot (Moving-Average-Crossover)

Nachbau des Ablaufs aus dem Video „Crypto Trading Bot with AI: The $10K Challenge“, erweitert um einen 4h-Trendfilter mit Long- und Short-Seite:

1. **Strategie:** Moving-Average-Crossover im **5-Minuten-Chart**, gefiltert durch den **4h-Trend** (siehe unten).
2. **Dashboard** mit Paper-Equity, Preis-Chart, MAs, Kauf/Verkauf-Markern und Trade-Liste.
3. **Live-Preise** über die CoinGecko-API.
4. **Backtest** auf historischen CoinGecko-Daten.
5. **Forward-Test** live: per REST (kostenlos) oder per CoinGecko-WebSocket mit Ticks unter einer Sekunde und 1-Sekunden-Kerzen.

> ⚠️ **Nur Papiergeld.** Der Bot sendet keine echten Orders und hat keinen Börsenzugang. Alle Ergebnisse sind simuliert. Keine Anlageberatung.

![Dashboard](docs/dashboard.png)

## Handelsregeln

Der 4h-Trend gilt als **bullisch**, wenn auf abgeschlossenen 4h-Kerzen der schnelle EMA (9) über dem langsamen EMA (21) liegt, und als **bärisch**, wenn er darunter liegt.

| 4h-Trend | 5-min Golden Cross (SMA 9 kreuzt SMA 21 nach oben) | 5-min Death Cross (nach unten) |
|---|---|---|
| bullisch | **Long eröffnen** | Long glattstellen |
| bärisch | Short glattstellen | **Short eröffnen** |

- Ein Cross gegen die offene Position stellt sie immer glatt. Das gilt auch dann, wenn der 4h-Trend inzwischen gedreht hat. Danach wird sofort in Trendrichtung neu eröffnet, wenn das Signal passt (z. B. Death Cross in bärischem Trend: Long schließen, dann Short eröffnen).
- Ein Trendwechsel allein schließt keine Position. Das passiert erst beim nächsten Gegen-Cross oder durch Stop-Loss bzw. Not-Aus.
- Solange der 4h-Trend noch nicht berechenbar ist, werden keine neuen Positionen eröffnet.
- Der Backtest nutzt eine 4h-Kerze erst ab ihrem Schlusszeitpunkt. Er schaut also nicht in die Zukunft.
- Shorts werden wie ein Futures-Short ohne Hebel simuliert. Funding- und Leihkosten sind nicht berücksichtigt.
- `--no-short`: im bärischen Trend nur flat bleiben (reiner Spot-Handel). `--no-trend`: altes Verhalten, Long bei jedem Golden Cross.

## Schnellstart

```bash
cd btc-bot
pip install -r requirements.txt

# Backtest: letzte 24 h in 5-min-Kerzen mit 4h-Trendfilter
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
| `--trend-interval` | 14400 | Trend-Zeitrahmen in Sekunden (14400 = 4h) |
| `--trend-fast` / `--trend-slow` / `--trend-ma` | 9 / 21 / `ema` | MAs für die Trendbestimmung |
| `--no-short` | – | keine Shorts, im bärischen Trend flat bleiben |
| `--no-trend` | – | Trendfilter aus: Long bei jedem Golden Cross |
| `--cash` | 10000 | Start-Kapital (Papier) |
| `--fee` / `--slippage` | 0.1 / 0.05 | Gebühr und Slippage pro Ausführung in % |
| `--stop-loss` | 3 | Stop-Loss in % gegen die Position (`0` = aus) |
| `--take-profit` | aus | Take-Profit in % |
| `--max-drawdown` | 20 | Not-Aus: Bei diesem Verlust vom Höchststand wird verkauft und der Handel gestoppt |
| `--fraction` | 100 | Anteil des Cash pro Einstieg in % |
| `--days` / `--interval` | 1 / 300 | Backtest-Zeitraum und Kerzenlänge in Sekunden |
| `--source` | `rest` | `rest` (kostenlos) oder `ws` (WebSocket, bezahlt) |
| `--candle-seconds` | 300 | Signal-Kerzenlänge im Forward-Test |
| `--reset` | – | gespeichertes Paper-Konto verwerfen |

CoinGecko-Granularität: `--days 1` liefert ~5-Minuten-Daten, 2–90 Tage stündliche, mehr als 90 Tage tägliche Daten.
**5-Minuten-Backtests gehen mit der kostenlosen API deshalb nur über die letzten 24 Stunden.** Für die 4h-Trendkerzen lädt der Bot automatisch stündliche Daten der letzten Tage nach.
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
  broker.py     Paper-Konto Long/Short: Gebühren, Slippage, Trade-Log
  engine.py     5-min-Signale + 4h-Trendfilter + Risiko-Regeln + Konto, identisch für Backtest und Live
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
- Mit 4h-Trendfilter, 5-min-Kerzen, letzte 24 h (06.11.2026): **−4 %** bei 7 Trades (0 Gewinner), Buy & Hold **+0,1 %**. Der Markt lief seitwärts, und jeder Trade zahlte rund 0,2 % Gebühren und Slippage.
Bevor echtes Geld ins Spiel kommt:

- Mit `--sweep` prüfen, ob auch *benachbarte* Einstellungen funktionieren, nicht nur die beste Zeile (sonst Overfitting).
- Mehrere Zeiträume testen (Bullen-, Bären-, Seitwärtsmarkt).
- Wochenlang im Forward-Test laufen lassen und mit dem Backtest vergleichen.
- Die installierten Claude-Skills `backtest-expert`, `walk-forward-validation` und `risk-management` helfen dabei.

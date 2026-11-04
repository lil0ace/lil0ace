# BTC-Tradingbot mit Claude – nützliche GitHub-Projekte

Recherche vom 04.11.2026 über die GitHub-Suche. Sterne und letztes Update zum Zeitpunkt der Suche.

> ⚠️ **Sicherheit zuerst:** Viele kleine Trading-Repos sind schlecht gepflegt oder sogar Malware, die API-Keys abgreift.
> Bevor du etwas verwendest: Code lesen, API-Keys **ohne Auszahlungsrecht** und mit IP-Whitelist anlegen,
> zuerst nur Paper-/Testnet-Trading. Ein LLM sollte nie ohne feste Limits (Positionsgröße, Stop-Loss, Kill-Switch) handeln.

## Empfohlene Architektur

Ein klassisches, deterministisches Bot-Framework führt die Trades aus; Claude hilft beim Entwickeln,
Backtesten und Überwachen, statt jede Order selbst zu platzieren.

```
Claude Code (Skills + MCP)  ──►  Freqtrade / Hummingbot / Jesse  ──►  Börse (via CCXT)
        ▲                                   │
        └──── Monitoring, Logs, Alerts ◄────┘
```

## 1. Bot-Frameworks (das Fundament)

| Repo | ⭐ | Wofür |
|---|---|---|
| [freqtrade/freqtrade](https://github.com/freqtrade/freqtrade) | 56k | Bekanntester Open-Source-Kryptobot (Python): Backtesting, Hyperopt, Telegram, Dry-Run, REST-API |
| [freqtrade/frequi](https://github.com/freqtrade/frequi) | 1.1k | Web-UI für Freqtrade |
| [freqtrade/freqtrade-strategies](https://github.com/freqtrade/freqtrade-strategies) | 5.6k | Beispielstrategien |
| [hummingbot/hummingbot](https://github.com/hummingbot/hummingbot) | 21k | Market Making / Arbitrage, Docker-Deployments |
| [jesse-ai/jesse](https://github.com/jesse-ai/jesse) | 8.8k | Saubere Python-Strategien + Backtests |
| [nautechsystems/nautilus_trader](https://github.com/nautechsystems/nautilus_trader) | 31k | Professionelle, ereignisgesteuerte Engine (Rust/Python) |
| [ccxt/ccxt](https://github.com/ccxt/ccxt) | 45k | Einheitliche API für 100+ Börsen – Basis fast aller anderen Tools |

## 2. MCP-Server: Claude mit Bot & Börse verbinden

| Repo | ⭐ | Wofür |
|---|---|---|
| [kukapay/freqtrade-mcp](https://github.com/kukapay/freqtrade-mcp) | 149 | Claude steuert/abfragt einen laufenden Freqtrade-Bot über dessen REST-API (Status, Trades, Profit) – **ideal zum "am Laufen halten"** |
| [dasein108/freqtrade_dev_mcp](https://github.com/dasein108/freqtrade_dev_mcp) | 10 | Backtesting, Hyperopt und Marktdaten aus Claude heraus |
| [yalcin/freqtrade-mcp](https://github.com/yalcin/freqtrade-mcp) | 18 | Read-only: gibt Claude Wissen über Freqtrade-Code → bessere Strategien |
| [hummingbot/mcp](https://github.com/hummingbot/mcp) | 59 | Offizieller Hummingbot-MCP-Server |
| [doggybee/mcp-server-ccxt](https://github.com/doggybee/mcp-server-ccxt) | 145 | CCXT als MCP: Kurse, Orderbuch, Orders auf vielen Börsen |
| [lazy-dinosaur/ccxt-mcp](https://github.com/lazy-dinosaur/ccxt-mcp) | 95 | Alternative CCXT-MCP mit Trading-Funktionen |
| [krakenfx/kraken-cli](https://github.com/krakenfx/kraken-cli) | 797 | **Offiziell von Kraken**: CLI mit eingebautem MCP-Server |
| [btschwertfeger/python-kraken-sdk](https://github.com/btschwertfeger/python-kraken-sdk) | 87 | Kraken SDK + CLI + MCP |
| [Bitget-AI/agent_hub](https://github.com/Bitget-AI/agent_hub) | 234 | **Offiziell von Bitget**: Toolkit für Claude/Cursor |
| [alpacahq/alpaca-mcp-server](https://github.com/alpacahq/alpaca-mcp-server) | 1k | **Offiziell von Alpaca**: Aktien + Krypto, gutes Paper-Trading |
| [nirholas/Binance-MCP](https://github.com/nirholas/Binance-MCP) / [AnalyticAce/binance-mcp-server](https://github.com/AnalyticAce/binance-mcp-server) | 40 / 51 | Inoffizielle Binance-MCP-Server |
| [kukapay/crypto-orderbook-mcp](https://github.com/kukapay/crypto-orderbook-mcp) | 16 | Orderbuch-Tiefe/Imbalance über mehrere Börsen |

Übersichtslisten: [BlockRunAI/awesome-finance-mcp](https://github.com/BlockRunAI/awesome-finance-mcp) (258 ⭐),
[badkk/awesome-crypto-mcp-servers](https://github.com/badkk/awesome-crypto-mcp-servers) (147 ⭐),
[narekgevorgyan/crypto-mcp-servers](https://github.com/narekgevorgyan/crypto-mcp-servers).

## 3. Claude-Code-Skills & Workflows für Trading

| Repo | ⭐ | Wofür |
|---|---|---|
| [tradermonty/claude-trading-skills](https://github.com/tradermonty/claude-trading-skills) | 3.6k | Große Skill-Sammlung: Marktanalyse, Charttechnik, Wirtschaftskalender (eher Aktien, gut übertragbar) |
| [agiprolabs/claude-trading-skills](https://github.com/agiprolabs/claude-trading-skills) | 509 | 68 Skills für Trading, DeFi und Quant |
| [Trade-With-Claude/cbt-framework](https://github.com/Trade-With-Claude/cbt-framework) | 78 | Backtesting-Framework für Claude Code: von der Idee bis Live, 21 Commands |
| [hugoguerrap/crypto-claude-desk](https://github.com/hugoguerrap/crypto-claude-desk) | 89 | Multi-Agent-Krypto-Analyse mit Claude Code (6 Agents, MCP-Tools) |
| [Blave-TW/blave-quant-skill](https://github.com/Blave-TW/blave-quant-skill) | 42 | Krypto-Alpha-Daten + Börsen-Referenz als Skill |
| [MobiusQuant/OpenMobius-skill](https://github.com/MobiusQuant/OpenMobius-skill) | 721 | ICT/SMC-Trading-Wissen als Skill |
| [pedrobraiti/vizier-trading-skill](https://github.com/pedrobraiti/vizier-trading-skill) | 8 | "Entscheidungs-Gehirn"-Skill (Recherche → Entscheidung) |

## 4. Komplette KI-Trading-Agenten (zum Lernen/Abschauen)

| Repo | ⭐ | Notiz |
|---|---|---|
| [qrak/LLM_trader](https://github.com/qrak/LLM_trader) | 141 | LLM-Agent, der Chart, Prompt, Gedächtnis und Verluste transparent macht (Paper-Trading) |
| [BijectiveLabs/bitra](https://github.com/BijectiveLabs/bitra) | 47 | "Agenten schlagen vor, das System entscheidet" – gutes Sicherheitsmuster |
| [mnemox-ai/tradememory-protocol](https://github.com/mnemox-ai/tradememory-protocol) | 1.4k | Entscheidungs-Audit-Trail + Gedächtnis für Trading-Agents |
| [alsk1992/CloddsBot](https://github.com/alsk1992/CloddsBot) | 3k | Großer autonomer Agent (Binance, Hyperliquid, Polymarket …) – vor Nutzung gründlich prüfen |
| [Lumiwealth/lumibot](https://github.com/Lumiwealth/lumibot) | 2.2k | Python-Framework mit KI-Agents, Backtest/Paper/Live |
| [joubja/PaperTradingBot](https://github.com/joubja/PaperTradingBot) | – | Ehrlicher Vergleich "KI-Bots vs. HODL" – lohnt sich als Realitätscheck |

## 5. Betrieb: den Bot am Laufen halten

- **Freqtrade/Hummingbot in Docker** mit `restart: unless-stopped` (Beispiele: [hummingbot/deploy](https://github.com/hummingbot/deploy)).
- **Telegram-Bot von Freqtrade** für Alerts und `/status`, `/stop`, `/forceexit`.
- **freqtrade-mcp** + Claude Code: Bot-Zustand per Chat prüfen, Logs analysieren, Probleme debuggen.
- **Claude-Code-Hooks** als Schutz, z. B. [Dicklesworthstone/destructive_command_guard](https://github.com/Dicklesworthstone/destructive_command_guard) (blockiert gefährliche Befehle);
  Beispiel-Setups: [ChrisWiles/claude-code-showcase](https://github.com/ChrisWiles/claude-code-showcase), [FlorianBruniaux/claude-code-ultimate-guide](https://github.com/FlorianBruniaux/claude-code-ultimate-guide).
- Geplante Claude-Läufe (z. B. täglicher Health-Check: Läuft der Container? Drawdown? Offene Orders?) mit Report per Mail/Telegram.

## Vorgeschlagener Einstieg

1. `freqtrade` per Docker installieren, BTC/USDT, **dry-run** aktivieren.
2. Strategie mit Claude Code schreiben; als Kontext `yalcin/freqtrade-mcp` oder `tradermonty/claude-trading-skills` nutzen.
3. Backtests/Hyperopt (`dasein108/freqtrade_dev_mcp` oder Freqtrade-CLI) – Out-of-Sample prüfen!
4. Wochenlang Paper-Trading, Überwachung über `kukapay/freqtrade-mcp` + Telegram.
5. Erst dann live, mit kleinem Betrag, Keys ohne Auszahlungsrecht, harten Limits.

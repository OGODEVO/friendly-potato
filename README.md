# 🏀 NBA Sharp — Multi-Agent Betting Analyst

A Telegram bot powered by **two competing AI agents** that debate NBA matchups, pull live data, and give structured betting recommendations — each running on a different LLM.

![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)

---

## How It Works

```
You (Telegram)
  │
  ▼
📊 Agent A: "The Sharp"          ──── GPT-5.1 (OpenAI)
│  Quant analyst. eFG%, OffRtg,
│  DefRtg, pace. No narratives.
│
  ▼
🎯 Agent B: "The Contrarian"     ──── Kimi-k2.5 (Novita AI)
│  Market psychologist. Spots,
│  public fades, value traps.
│
  ▼
🤝 Consensus Card
   Pick · Confidence · Reason
```

Both agents share the same NBA data tools but approach games from opposite angles. After both respond, a **consensus card** compares their picks.

---

## Features

- **Multi-LLM debate** — Two agents on different models for genuine diversity of thought
- **Live box scores** — Real-time game data via Rolling Insights API
- **Market odds** — Spreads, moneylines, and totals via The Odds API
- **Streaming responses** — Token-by-token output in Telegram with a typing cursor (`▌`)
- **Structured picks** — Each agent ends with a `Pick / Confidence / Reason` card
- **Consensus logic** — Automatic agreement/disagreement detection after both agents respond
- **Per-chat history** — 30-message rolling window per Telegram chat

---

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/OGODEVO/friendly-potato.git
cd friendly-potato
python -m venv venv && source venv/bin/activate
pip install openai httpx python-dotenv pyyaml python-telegram-bot rich
```

### 2. Configure API Keys

Create a `.env` file:

```env
OPENAI_API_KEY=sk-...        # OpenAI (Agent A)
NOVITA_API_KEY=sk_...         # Novita AI (Agent B)
TELEGRAM_BOT_TOKEN=...        # Telegram BotFather token
RSC_TOKEN=...                 # Rolling Insights NBA data API
ODDS_API_KEY=...              # The Odds API (optional, for market odds)
```

### 3. Run

```bash
python main.py
```

Then message your bot on Telegram. Ask it anything:

> *"Warriors vs Lakers tonight"*
> *"Who should I bet on — Celtics or Knicks?"*
> *"Give me the 76ers live score and a prediction"*

---

## Agent Personas

| Agent | Name | Focus | Model | Temp |
|-------|------|-------|-------|------|
| A | **The Sharp** | eFG%, OffRtg/DefRtg, pace, math edges | `gpt-5.1` | 0.4 |
| B | **The Contrarian** | Market psychology, spots, public fades, value | `kimi-k2.5` | 0.6 |

Each agent outputs a **decision card**:

```
Pick: Lakers -3.5
Confidence: 72
Reason: +5.2 NetRtg edge, injuries favor LAL, line hasn't moved.
```

---

## Available Tools

| Tool | Description |
|------|-------------|
| `get_daily_schedule` | Today's games |
| `get_weekly_schedule` | 7-day schedule |
| `get_live_scores` | Live box scores (auto-resolves game ID) |
| `get_team_stats` | Season team stats |
| `get_player_stats` | Season player stats |
| `get_injuries` | Current injury report |
| `get_depth_chart` | Roster depth |
| `get_team_details` | Team metadata |
| `get_player_info` | Player metadata |
| `get_market_odds` | Live spreads/ML/totals from The Odds API |

---

## Project Structure

```
├── main.py                  # Telegram bot, streaming, consensus logic
├── config/
│   └── config.yaml          # Per-agent model/provider config
├── agents/
│   ├── base_agent.py        # OpenAI client, streaming, tool-call loop
│   ├── analyst.py           # Agent A — The Sharp
│   └── strategist.py        # Agent B — The Contrarian
├── tools/
│   ├── nba_client.py        # Rolling Insights API client
│   ├── nba_tools.py         # Agent-facing tool functions + schemas
│   ├── odds_client.py       # The Odds API client
│   └── team_lookup.py       # Team name → API ID (verified)
├── agent.md                 # Project context for AI assistants
├── .env                     # API keys (gitignored)
└── pyproject.toml           # Project metadata
```

---

## Telegram Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/reset` | Clear chat history |

---

## Configuration

Edit `config/config.yaml` to swap models or providers:

```yaml
agents:
  agent_1:
    model: "gpt-5.1"       # Any OpenAI model
    provider: "openai"

  agent_2:
    model: "moonshotai/kimi-k2.5"
    provider: "novita"
    base_url: "https://api.novita.ai/openai"
```

Any OpenAI-compatible API works — just set the `base_url` and corresponding key in `.env`.

---

## Known Gotchas

| Issue | Detail |
|-------|--------|
| **Timezone** | Dates use US Eastern (NBA standard), not UTC |
| **Live endpoint** | Pass `team_id` OR `game_id`, never both |
| **Team IDs** | All 30 verified against API — don't guess |
| **Novita rate limit** | 30 RPM for kimi-k2.5 (comfortable for single user) |
| **`max_completion_tokens`** | Required by gpt-5.1; Novita/Kimi may need `max_tokens` instead |

---

## License

MIT

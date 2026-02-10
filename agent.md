# NBA Betting Analytics – Telegram Bot

## What This Is
A Telegram bot with **two AI agents** that debate NBA games and give betting recommendations. Each agent has a distinct personality and runs on a different LLM.

## Architecture
```
User (Telegram) → main.py → Agent A → Agent B → Telegram
                               ↓           ↓
                          tools/nba_tools.py (shared)
                               ↓
                     Rolling Insights NBA API
```

## Agents

| Agent | Name | Role | Model | Temp |
|-------|------|------|-------|------|
| A | **The Sharp** | Cold quant analyst. Only cares about eFG%, OffRtg/DefRtg, pace. No narratives. | `gpt-5.1` (OpenAI) | 0.4 |
| B | **The Contrarian** | Market psychologist. Fades the public, finds traps, ignores stats. | `moonshotai/kimi-k2.5` (Novita AI) | 0.6 |

## Key Files
- `main.py` – Telegram bot entry point, streaming responses, per-chat history (30 msg cap)
- `agents/base_agent.py` – OpenAI client wrapper with streaming + tool call loop
- `agents/analyst.py` – Agent A prompt + class
- `agents/strategist.py` – Agent B prompt + class
- `config/config.yaml` – Per-agent model/provider config
- `tools/nba_tools.py` – Agent-facing tool functions (schedule, stats, injuries, live scores, depth charts)
- `tools/nba_client.py` – HTTP client for Rolling Insights API
- `tools/team_lookup.py` – Team name → API ID mapping (verified against API)

## APIs & Auth (`.env`)
```
OPENAI_API_KEY=       # For Agent A (The Sharp)
NOVITA_API_KEY=       # For Agent B (The Contrarian) – base_url: https://api.novita.ai/openai
TELEGRAM_BOT_TOKEN=   # Telegram Bot API
RSC_TOKEN=            # Rolling Insights NBA data API
RSC_BASE_URL=         # Optional override (default: https://rest.datafeeds.rolling-insights.com/api/v1)
ODDS_API_KEY=         # Odds API key for market prices (h2h/spreads/totals)
ODDS_API_BASE_URL=    # Optional override (default: https://api.the-odds-api.com/v4)
```

## Available NBA Tools
| Tool | What it does |
|------|-------------|
| `get_daily_schedule(date, team_name)` | Today's games |
| `get_weekly_schedule(date, team_name)` | 7-day schedule |
| `get_season_schedule(year, team_name)` | Full season |
| `get_live_scores(date, team_name)` | Live box scores (auto-resolves game_id) |
| `get_team_stats(year, team_name)` | Season team stats |
| `get_player_stats(year, team_name)` | Season player stats |
| `get_injuries(team_name)` | Current injury report |
| `get_depth_charts(team_name)` | Roster depth |
| `get_team_info(team_name)` | Team metadata |
| `get_player_info(team_name)` | Player metadata |
| `get_market_odds(...)` | Market prices (h2h/spreads/totals/outrights), with optional team/bookmaker/time filters |

## Known Gotchas
- **Timezone**: `_get_today()` uses US Eastern (`UTC-5`), not UTC. NBA schedules are in ET.
- **Live endpoint**: Pass EITHER `team_id` OR `game_id`, never both (API returns 404).
- **Team IDs**: All 30 verified against the API. Do NOT guess IDs.
- **Novita rate limit**: 30 RPM for kimi-k2.5. Comfortable for single-user bot.
- **Streaming**: Responses stream to Telegram via periodic `editMessageText` (~0.8s intervals) with a `▌` cursor.
- **`max_completion_tokens`**: Used instead of `max_tokens` (required by gpt-5.1). If Novita/Kimi rejects this param, switch back to `max_tokens` for that agent only.

## Pending Work
1. **Persistent chat history**: Currently in-memory dict, lost on restart. Could add JSON file persistence.

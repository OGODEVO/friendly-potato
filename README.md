# NBA Betting Telegram Bot

A Telegram bot with two specialized analysis agents and one normal-chat assistant.

## System Design

The bot has two operating paths:

1. Normal chat path (single assistant)
- Used for casual messages.
- Shows: `Assistant is thinking...`
- No forced betting pick output.

2. Analysis path (two agents + consensus)
- Used when analysis intent is detected, or forced with `/analysis`.
- Shows:
  - `The Sharp is thinking...`
  - `The Contrarian is thinking...`
- Ends with a consensus block.

## Mode Routing

Per chat, mode can be:

1. `auto` (default after `/reset`)
- Normal chat unless betting-analysis intent is detected.

2. `analysis`
- Always runs the two-agent analysis path.

3. `normal`
- Always runs the single assistant path.

Commands:

- `/start` show help
- `/analysis` force analysis mode
- `/normal` force normal chat mode
- `/auto` return to intent-based routing
- `/reset` clear history and reset mode to `auto`

## Analysis Workflow

On analysis turns, the bot injects `SKILL.md` as the analysis playbook.

Current analysis policy includes:

- Live-first workflow via `get_live_vs_season_context(...)`
- Roster grounding via `get_roster_context(...)`
- Market grounding via `get_market_odds(...)`
- Structured output card:
  - `Pick`
  - `Confidence`
  - `Reason`

## Agent Roles

1. The Sharp (`gpt-5.1`)
- Quant/stat-driven analysis.

2. The Contrarian (`moonshotai/kimi-k2.5` via Novita)
- Market/spot/value framing.

Important: both prompts now require tool-grounded roster/market claims (not model memory).

## Tooling (Exposed to Agents)

- `get_daily_schedule`
- `get_live_scores`
- `get_live_vs_season_context`
- `get_team_stats`
- `get_player_info`
- `get_player_stats`
- `get_injuries`
- `get_depth_chart`
- `get_roster_context`
- `get_market_odds`

## Caching Behavior

In-memory TTL cache is implemented in `tools/nba_tools.py`.

Cached endpoints include schedules/stats/roster/odds.

Not cached (always fresh):

- `get_live_scores`
- `get_live_vs_season_context`

Notes:

- Cache is process-local and clears on bot restart.
- Daily schedule cache is ET-aware (today cached until next ET midnight).

## Project Structure

- `main.py` Telegram runtime, mode routing, streaming, consensus
- `SKILL.md` analysis playbook used during analysis turns
- `agents/base_agent.py` model client + tool-call loop
- `agents/analyst.py` The Sharp prompt
- `agents/strategist.py` The Contrarian prompt
- `tools/nba_tools.py` tool definitions, cache, orchestration
- `tools/nba_client.py` Rolling Insights client
- `tools/odds_client.py` Odds API client
- `config/config.yaml` model/provider config
- `agent.md` internal project context notes

## Environment Variables

Set in `.env`:

- `OPENAI_API_KEY`
- `NOVITA_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `RSC_TOKEN`
- `RSC_BASE_URL` (optional)
- `ODDS_API_KEY`
- `ODDS_API_BASE_URL` (optional)

## Run

```bash
cd .
python main.py
```

## Operational Notes

- Time logic is ET-based for NBA date handling.
- Live endpoint logic resolves `game_id` from schedule when `team_name` is provided.
- If roster or odds data cannot be verified from tools, analysis should explicitly mark it unverified.

---
name: nba-analysis-playbook
description: Workflow for NBA betting analysis turns. Use this when the user asks for picks, odds-based analysis, or live-game betting decisions.
---

# NBA Analysis Playbook

## Trigger
Use this playbook only for analysis requests (picks, lines, odds, live betting, EV, confidence).

## Required Workflow
1. Identify the target game/team and market request (h2h, spread, total, or no-bet decision).
2. For live analysis, call `get_live_vs_season_context(team_name, include_roster=true, include_market=true)` first.
3. For roster-sensitive claims, verify with `get_roster_context(team_name)` and use `summary.projected_starters`, `summary.rotation_players_depth_1_to_3`, and `summary.injury_players`.
4. For market/value claims, verify with `get_market_odds(...)` or user-provided odds.
5. If required data is missing, explicitly mark it unverified and lower confidence.

## Decision Rules
1. Do not force a bet when edge is unclear.
2. Prefer `NO BET` over weak or unverified edge.
3. Separate evidence from narrative; do not invent market or roster facts.
4. Never use model memory/training data for roster facts; roster must come from tool outputs.
5. If roster data is missing or conflicting, state: "Roster data unverified."

## Output Contract
End with exactly:

Pick: <team/side | over | under | no bet>
Confidence: <0-100>
Reason: <one sentence, max 20 words>

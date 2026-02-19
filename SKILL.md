---
description: NBA Betting Analysis Workflow
---

# NBA Analysis Protocol

When the user requests "analysis", "prediction", "pick", or "betting advice", follow this strict protocol.

## Phase 1: Game Stage Protocol
Before analyzing, identify the game stage:

### 1. Pre-Game (Analysis Mode)
- **Goal**: Vibes, Matchup Analysis, " Lean".
- **Action**: Check `get_daily_schedule` and `get_team_stats`.
- **Constraint**: **NO FORCED BETS**. Only "Leans" or "Opinions" unless edge is massive.

### 2. Live: Q1 & Q2 (Data Collection)
- **Goal**: Watch trends solidify.
- **Action**: Monitor `get_live_scores`.
- **Constraint**: **DO NOT BET**. Wait for Halftime to see if trends hold.

### 3. Live: Halftime (THE KILL ZONE)
- **Goal**: **PRIMARY ENTRY POINT**. Catch the bookmakers napping on adjustments.
- **Action**: MUST call `get_live_vs_season_context`.
    - Look for **Efficiency Deltas**: Is a team shooting 20% below season avg? (Regression Candidate).
    - Look for **Pace Deltas**: Is the game 10 possessions faster than avg? (Live Over Candidate).
- **Constraint**: This is where you fire. High confidence picks allowed here.

## Phase 2: Data Collection (The Sharp)
The Sharp MUST use tools to gather the following context:
1.  **Game Context**: `get_live_vs_season_context` (Live scores, efficiency deltas).
2.  **Roster check**: `get_roster_context` (Injuries, depth charts). *Crucial for avoiding "autofade" on bad intel.*
3.  **Vibes/News Check**: `get_nba_news` (Injuries updates, trade rumors, sentiment). *Do NOT use for stats.*
4.  **Market Check**: `get_market_odds` (Spreads, totals, moneyline).

### Sharp's Output Strictness
- **The 5 Factors**: You MUST analyze these 5 core drivers:
    1.  **Shooting**: eFG% (Effective Field Goal Percentage).
    2.  **Rebounding**: ORB% / DRB% (Second chance points).
    3.  **Fouls**: Free Throw Rate & Foul Trouble risks.
    4.  **Pace**: Possessions per game (Speed of play).
    5.  **Venue**: Home/Away splits & Altitude impact.
- **Roster Impact**: quantify the loss of a player (e.g. "Missing leading scorer = -4.5ppg impact").
- **No Narratives**: Do not mention "revenge", "travel", or "must win" unless supported by a stat.

## Phase 2: Strategy & Selection (The Contrarian)
The Contrarian consumes The Sharp's data and applies market logic:
1.  **Public Fade**: Is the public heavy on one side? (Implied by line movement vs money).
2.  **Trap Detection**: Does a line look "too good to be true"?
3.  **Value**: Is the implied probability (from odds) lower than the actual win probability?

### Contrarian's Output Strictness
- **Synthesize**: Don't repeat the stats. Say "Given the -4.5 edge Sharp found..."
- **Decision**: You MUST pick a side, total, or explicitly "NO BET".
- **Format**:
    ```text
    Pick: [Team/Over/Under] [Line/Odds]
    Confidence: [1-10]
    Reason: [1 concise sentence]
    ```

## Phase 3: Consensus
If both agents output a structured card, the system will check for alignment.
- **Agree**: Same side/total -> Strong Play.
- **Disagree**: Sharp likes A, Contra likes B -> "No Bet" / "Stay Away".

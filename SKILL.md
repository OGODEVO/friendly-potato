---
description: NBA Betting Analysis Workflow
---

# NBA Analysis Protocol

When the user requests "analysis", "prediction", "pick", or "betting advice", follow this strict protocol.

## Phase 1: Game Stage Protocol
Before analyzing, identify the game stage:

### 1. Pre-Game (Analysis Mode)
- **Goal**: Vibes, Matchup Analysis, " Lean".
- **Action**: Check `get_pregame_context` (includes stats, opponent, roster, odds).
- **Constraint**: **NO FORCED BETS**. Only "Leans" or "Opinions" unless edge is massive.

### 2. Live: Q1 & Q2 (Data Collection)
- **Goal**: Watch trends solidify.
- **Action**: Monitor `get_live_scores`.
- **Constraint**: **DO NOT BET**. Wait for Halftime to see if trends hold.

### 3. Live: Halftime (THE KILL ZONE)
- **Goal**: **PRIMARY ENTRY POINT**. Catch the bookmakers napping on adjustments.
- **Action**: MUST call `get_live_vs_season_context`.
    - Look for **Efficiency Deltas**: Is a team shooting 20% below season avg? (Positive Regression Candidate -> Over potential). Is a team shooting unsustainably hot? (Negative Regression Candidate -> Under potential).
    - Look for **Pace Deltas**: Is the game much faster or slower than expected?
- **Constraint**: This is where you fire. High confidence picks allowed here.

## Phase 2: Data Collection (The Sharp)
The Sharp MUST use tools to gather the following context:
1.  **Game Context**: 
    - *Pre-Game*: Use `get_pregame_context` (Single call for stats, rosters, and odds).
    - *Halftime*: Use `get_live_vs_season_context` (Live scores, efficiency deltas).
2.  **Roster check**: `get_roster_context` (Injuries, depth charts). *Crucial for avoiding "autofade" on bad intel. (Already included in get_pregame_context)*
3.  **Late Scratch / Injury Check**: **CRITICAL STEP**. You MUST call `get_nba_news` to search for "[Team Name] injuries today" or "[Star Player] playing status" to confirm star availability before making a final read, as late scratches often break the season baselines.
4.  **Market Check**: `get_market_odds` (Spreads, totals, moneyline). *(Already included in get_pregame_context)*

### Sharp's Output Strictness
- **Never ask the user for current scores or game state.** The `get_live_vs_season_context` and `get_pregame_context` tools return the score, quarter, and time remaining in the `game` object JSON. Read it from there.
- **The 5 Factors**: You MUST analyze these 5 core drivers:
    1.  **Shooting**: eFG% (Effective Field Goal Percentage).
    2.  **Rebounding**: ORB% / DRB% (Second chance points).
    3.  **Fouls**: Free Throw Rate & Foul Trouble risks. (Note: High fouls mean clock stoppages and easy points, which heavily correlates to the OVER).
    4.  **Pace**: Possessions per game (Speed of play).
    5.  **Venue**: Home/Away splits & Altitude impact.
- **Roster Impact**: quantify the loss of a player (e.g. "Missing leading scorer = -4.5ppg impact").
- **No Narratives**: Do not mention "revenge", "travel", or "must win" unless supported by a stat.

## Phase 2: Strategy & Selection (The Contrarian)
The Contrarian consumes The Sharp's data and applies market logic:
1.  **Public Fade**: Is the public heavy on one side? (Implied by line movement vs money).
2.  **Trap Detection**: Does a line look "too good to be true"?
3.  **Value**: Is the implied probability (from odds) lower than the actual win probability?
4.  **Tool Usage**: While you normally rely on The Sharp's data gathering, if the user explicitly addresses you and asks you to pull data directly, you WILL use your data gathering tools.

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

from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
import json
from .nba_client import NBAClient
from .odds_client import OddsClient
from .team_lookup import resolve_team

client = NBAClient()
odds_client = OddsClient()

# NBA schedules use US Eastern Time
_ET = timezone(timedelta(hours=-5))

def _get_today() -> str:
    return datetime.now(_ET).strftime("%Y-%m-%d")

def _get_current_season_year() -> str:
    # Simple logic: if month is > 9 (Oct), it's start of season (e.g. 2023 for 23-24). 
    # If month < 9, it's end of season (still 2023 for 23-24 season usually in API logic, check docs carefully).
    # Docs say: "2017-2018 season = 2017"
    now = datetime.now(_ET)
    if now.month >= 10:
        return str(now.year)
    else:
        return str(now.year - 1)

# --- Agent Tools ---

def get_daily_schedule(date: str = None, team_name: str = None) -> str:
    """
    Get the NBA schedule for a specific date.
    
    Args:
        date (str, optional): Date in YYYY-MM-DD. Defaults to TODAY if not provided.
        team_name (str, optional): Filter by team name (e.g. "Lakers", "Warriors").
    """
    if not date: date = _get_today()
    
    team_id = None
    if team_name:
        team_id = resolve_team(team_name)
        if not team_id:
            return f"Error: Could not find team '{team_name}'. Please check spelling."

    data = client.get_schedule(date, team_id=team_id)
    return json.dumps(data)

def get_weekly_schedule(date: str = None, team_name: str = None) -> str:
    """
    Get the NBA schedule for 7 days starting from the given date.
    
    Args:
        date (str, optional): Start date in YYYY-MM-DD. Defaults to TODAY.
        team_name (str, optional): Filter by team name.
    """
    if not date: date = _get_today()
    
    team_id = None
    if team_name:
        team_id = resolve_team(team_name)
        if not team_id:
            return f"Error: Could not find team '{team_name}'."

    data = client.get_weekly_schedule(date, team_id=team_id)
    return json.dumps(data)

def _find_game_id_for_team(date: str, team_id: int) -> str | None:
    """
    Internal helper: Fetches the daily schedule and finds the game_id 
    for a specific team on a given date. This removes the need for 
    the agent to chain get_daily_schedule -> get_live_scores.
    """
    schedule_data = client.get_schedule(date, team_id=team_id)
    
    # Parse schedule response to find game_id
    if "error" in schedule_data:
        return None
    
    games = schedule_data.get("data", {}).get("NBA", [])
    if not games:
        return None
    
    # Return the first matching game_id (usually one per team per day)
    return games[0].get("game_ID")


def get_live_scores(date: str = None, team_name: str = None) -> str:
    """
    Get live scores and full boxscore data for games.
    
    SMART ORCHESTRATION: If you provide a team_name, this tool will 
    automatically look up today's schedule to find the correct game_id,
    then fetch the live boxscore for that specific game.
    No need to call get_daily_schedule first.
    
    Args:
        date (str, optional): Date in YYYY-MM-DD. Defaults to TODAY.
        team_name (str, optional): Team name (e.g. "Lakers", "Warriors").
                                   HIGHLY RECOMMENDED to get a specific game's boxscore.
    """
    if not date: date = _get_today()
    
    team_id = None
    game_id = None
    
    if team_name:
        team_id = resolve_team(team_name)
        if not team_id:
            return f"Error: Could not resolve team '{team_name}' to an ID."
        
        # SMART: Auto-resolve game_id from the daily schedule
        game_id = _find_game_id_for_team(date, team_id)
        if not game_id:
            return json.dumps({
                "info": f"No games found for {team_name} on {date}.",
                "suggestion": "Try a different date or check the weekly schedule."
            })
        # API requires EITHER team_id OR game_id, not both
        team_id = None

    data = client.get_live_data(date, team_id=team_id, game_id=game_id)
    return json.dumps(data)

def get_team_details(team_name: str = None) -> str:
    """
    Get general team info (Arena, Conference, etc.).
    
    Args:
        team_name (str, optional): Team name (e.g. "Celtics"). Returns all teams if omitted.
    """
    team_id = None
    if team_name:
        team_id = resolve_team(team_name)
        if not team_id:
            return f"Error: Could not resolve team '{team_name}'."
            
    data = client.get_team_info(team_id=team_id)
    return json.dumps(data)

def get_team_stats(team_name: str = None, year: str = None) -> str:
    """
    Get season-level team statistics.
    
    Args:
        team_name (str, optional): Team name (e.g. "Nuggets"). 
        year (str, optional): Season start year (e.g. "2023" for 23-24). Defaults to CURRENT season.
    """
    if not year: year = _get_current_season_year()
    
    team_id = None
    if team_name:
        team_id = resolve_team(team_name)
        if not team_id:
            return f"Error: Could not resolve team '{team_name}'."
            
    data = client.get_team_stats(year, team_id=team_id)
    return json.dumps(data)

def get_player_info(team_name: str = None) -> str:
    """
    Get list of players and their details (Position, Height, Age).
    
    Args:
        team_name (str, optional): Filter by team name. 
                                   HIGHLY RECOMMENDED to avoid listing every player in the league.
    """
    team_id = None
    if team_name:
        team_id = resolve_team(team_name)
        if not team_id:
            return f"Error: Could not resolve team '{team_name}'."
            
    data = client.get_player_info(team_id=team_id)
    return json.dumps(data)

def get_player_stats(team_name: str = None, year: str = None) -> str:
    """
    Get season-level player statistics.
    
    Args:
        team_name (str, optional): Filter by team name. 
        year (str, optional): Season start year. Defaults to CURRENT season.
    """
    if not year: year = _get_current_season_year()
    
    team_id = None
    if team_name:
        team_id = resolve_team(team_name)
        if not team_id:
            return f"Error: Could not resolve team '{team_name}'."
            
    data = client.get_player_stats(year, team_id=team_id)
    return json.dumps(data)

def get_injuries(team_name: str = None) -> str:
    """
    Get injury reports.
    
    Args:
        team_name (str, optional): Filter by team name.
    """
    team_id = None
    if team_name:
        team_id = resolve_team(team_name)
        if not team_id:
            return f"Error: Could not resolve team '{team_name}'."
            
    data = client.get_injuries(team_id=team_id)
    return json.dumps(data)

def get_depth_chart(team_name: str) -> str:
    """
    Get depth chart for a specific team.
    
    Args:
        team_name (str): Team name (e.g. "Bucks"). REQUIRED.
    """
    team_id = resolve_team(team_name)
    if not team_id:
        return f"Error: Could not resolve team '{team_name}'."
            
    data = client.get_depth_charts(team_id=team_id)
    return json.dumps(data)


def get_market_odds(
    sport: str = "basketball_nba",
    regions: str = "us",
    markets: str = "h2h",
    date_format: str = "iso",
    odds_format: str = "american",
    team_name: str = None,
    event_ids: str = None,
    bookmakers: str = None,
    commence_time_from: str = None,
    commence_time_to: str = None,
    include_links: bool = None,
    include_sids: bool = None,
    include_bet_limits: bool = None,
    include_rotation_numbers: bool = None,
) -> str:
    """
    Get market odds (moneyline / spread / totals) from Odds API.

    Args:
        sport (str, optional): Sport key. Default "basketball_nba".
        regions (str, optional): Region list, e.g. "us" or "us,eu".
        markets (str, optional): "h2h", "spreads", "totals", comma-separated allowed.
        date_format (str, optional): "iso" or "unix".
        odds_format (str, optional): "american" or "decimal".
        team_name (str, optional): Optional team filter. Returns only matching events.
        event_ids (str, optional): Comma-separated event IDs.
        bookmakers (str, optional): Comma-separated bookmaker keys.
        commence_time_from (str, optional): ISO timestamp lower bound.
        commence_time_to (str, optional): ISO timestamp upper bound.
        include_links/include_sids/include_bet_limits/include_rotation_numbers (bool, optional): API flags.
    """
    data = odds_client.get_odds(
        sport=sport,
        regions=regions,
        markets=markets,
        date_format=date_format,
        odds_format=odds_format,
        event_ids=event_ids,
        bookmakers=bookmakers,
        commence_time_from=commence_time_from,
        commence_time_to=commence_time_to,
        include_links=include_links,
        include_sids=include_sids,
        include_bet_limits=include_bet_limits,
        include_rotation_numbers=include_rotation_numbers,
    )

    if "error" in data:
        return json.dumps(data)

    if team_name:
        needle = team_name.strip().lower()
        events = data.get("data", [])
        filtered = []
        for event in events:
            home = str(event.get("home_team", "")).lower()
            away = str(event.get("away_team", "")).lower()
            if needle in home or needle in away:
                filtered.append(event)

        data["data"] = filtered
        data["meta"] = data.get("meta", {})
        data["meta"]["team_filter"] = team_name
        data["meta"]["events_returned"] = len(filtered)

    return json.dumps(data)

# Tool Definitions for OpenAI
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "get_daily_schedule",
            "description": "Get NBA games schedule for a specific date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Date in YYYY-MM-DD. Default: Today."},
                    "team_name": {"type": "string", "description": "Team filter (e.g. 'Lakers')."}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_live_scores",
            "description": "Get live scores and full boxscores. Automatically finds the correct game when you provide a team name - no need to look up game IDs first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Date in YYYY-MM-DD. Default: Today."},
                    "team_name": {"type": "string", "description": "Team name (e.g. 'Lakers'). Highly recommended."}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_team_stats",
            "description": "Get season stats for a team.",
            "parameters": {
                "type": "object",
                "properties": {
                    "team_name": {"type": "string", "description": "Team name (e.g. 'Denver')."},
                    "year": {"type": "string", "description": "Season start year. DO NOT SET THIS unless the user asks for a specific past season. Current season is used automatically."}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_player_stats",
            "description": "Get player season stats.",
            "parameters": {
                "type": "object",
                "properties": {
                    "team_name": {"type": "string", "description": "Team name (e.g. 'Warriors'). Filter by team."},
                    "year": {"type": "string", "description": "Season start year. DO NOT SET THIS unless the user asks for a specific past season. Current season is used automatically."}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_injuries",
            "description": "Get injury report.",
            "parameters": {
                "type": "object",
                "properties": {
                    "team_name": {"type": "string", "description": "Team name (e.g. 'Heat')."}
                }
            }
        }
    },
     {
        "type": "function",
        "function": {
            "name": "get_depth_chart",
            "description": "Get team depth chart / rotation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "team_name": {"type": "string", "description": "Team name (e.g. 'Bucks')."}
                },
                "required": ["team_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_market_odds",
            "description": "Get live betting market odds (h2h/spreads/totals). Use this before making market-based claims.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sport": {"type": "string", "description": "Sport key, default 'basketball_nba'. Use 'upcoming' for cross-sport upcoming events."},
                    "regions": {"type": "string", "description": "Bookmaker regions, e.g. 'us' or 'us,eu'."},
                    "markets": {"type": "string", "description": "Comma-separated markets: h2h,spreads,totals,outrights."},
                    "date_format": {"type": "string", "description": "Timestamp format: iso or unix."},
                    "odds_format": {"type": "string", "description": "Odds format: american or decimal."},
                    "team_name": {"type": "string", "description": "Optional team filter (e.g. 'Lakers')."},
                    "event_ids": {"type": "string", "description": "Optional comma-separated event ids."},
                    "bookmakers": {"type": "string", "description": "Optional comma-separated bookmaker keys."},
                    "commence_time_from": {"type": "string", "description": "Optional ISO-8601 lower bound."},
                    "commence_time_to": {"type": "string", "description": "Optional ISO-8601 upper bound."},
                    "include_links": {"type": "boolean", "description": "Include bookmaker deep links if available."},
                    "include_sids": {"type": "boolean", "description": "Include source IDs if available."},
                    "include_bet_limits": {"type": "boolean", "description": "Include bet limits if available."},
                    "include_rotation_numbers": {"type": "boolean", "description": "Include rotation numbers if available."}
                }
            }
        }
    }
]

AVAILABLE_TOOLS = {
    "get_daily_schedule": get_daily_schedule,
    "get_live_scores": get_live_scores,
    "get_team_stats": get_team_stats,
    "get_player_stats": get_player_stats,
    "get_injuries": get_injuries,
    "get_depth_chart": get_depth_chart,
    "get_market_odds": get_market_odds
}


from datetime import datetime, timezone
from typing import Dict, Any, Optional
import json
from .nba_client import NBAClient
from .team_lookup import resolve_team

client = NBAClient()

def _get_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def _get_current_season_year() -> str:
    # Simple logic: if month is > 9 (Oct), it's start of season (e.g. 2023 for 23-24). 
    # If month < 9, it's end of season (still 2023 for 23-24 season usually in API logic, check docs carefully).
    # Docs say: "2017-2018 season = 2017"
    now = datetime.now(timezone.utc)
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
    }
]

AVAILABLE_TOOLS = {
    "get_daily_schedule": get_daily_schedule,
    "get_live_scores": get_live_scores,
    "get_team_stats": get_team_stats,
    "get_player_stats": get_player_stats,
    "get_injuries": get_injuries,
    "get_depth_chart": get_depth_chart
}

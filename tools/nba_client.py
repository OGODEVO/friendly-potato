
import os
import httpx
from typing import Dict, Any, Optional
from dotenv import load_dotenv
import logging

load_dotenv()

BASE_URL = os.getenv("RSC_BASE_URL", "https://rest.datafeeds.rolling-insights.com/api/v1")
RSC_TOKEN = os.getenv("RSC_TOKEN")

logger = logging.getLogger(__name__)

class NBAClient:
    def __init__(self):
        if not RSC_TOKEN:
            logger.warning("RSC_TOKEN not found in environment variables. API calls will fail.")
        
        self.headers = {
            "Accept": "application/json"
        }
    
    def _make_request(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Internal method to make HTTP GET requests to the NBA API.
        """
        if params is None:
            params = {}
            
        # Add required RSC_token
        params['RSC_token'] = RSC_TOKEN
        
        url = f"{BASE_URL}/{endpoint}"
        
        try:
            response = httpx.get(url, params=params, headers=self.headers, timeout=10.0)
            
            # Log the full URL for debugging (masking token in real logs ideally)
            # logger.info(f"Requesting: {response.url}")
            
            if response.status_code == 200:
                try:
                    return response.json()
                except Exception as e:
                    return {"error": "Failed to parse JSON response", "raw": response.text}
            elif response.status_code == 304:
                return {"status": "No data updates (304)"}
            elif response.status_code == 404:
                return {"error": "Resource not found (404)", "message": response.text}
            else:
                return {"error": f"API Error {response.status_code}", "message": response.text}
                
        except httpx.RequestError as e:
            return {"error": f"Request failed: {str(e)}"}

    def get_schedule(self, date_str: str, sport: str = "NBA", team_id: Optional[int] = None, game_id: Optional[str] = None) -> Dict[str, Any]:
        """Daily Schedule"""
        params = {}
        if team_id: params['team_id'] = team_id
        if game_id: params['game_id'] = game_id
        return self._make_request(f"schedule/{date_str}/{sport}", params)

    def get_weekly_schedule(self, date_str: str, sport: str = "NBA", team_id: Optional[int] = None) -> Dict[str, Any]:
        """Weekly Schedule"""
        params = {}
        if team_id: params['team_id'] = team_id
        return self._make_request(f"schedule-week/{date_str}/{sport}", params)

    def get_live_data(self, date_str: str, sport: str = "NBA", team_id: Optional[int] = None, game_id: Optional[str] = None) -> Dict[str, Any]:
        """Live Feed"""
        params = {}
        if team_id: params['team_id'] = team_id
        if game_id: params['game_id'] = game_id
        return self._make_request(f"live/{date_str}/{sport}", params)

    def get_team_info(self, sport: str = "NBA", team_id: Optional[int] = None) -> Dict[str, Any]:
        """Team Info"""
        params = {}
        if team_id: params['team_id'] = team_id
        return self._make_request(f"team-info/{sport}", params)

    def get_team_stats(self, year: str, sport: str = "NBA", team_id: Optional[int] = None) -> Dict[str, Any]:
        """Team Season Stats"""
        params = {}
        if team_id: params['team_id'] = team_id
        return self._make_request(f"team-stats/{year}/{sport}", params)

    def get_player_info(self, sport: str = "NBA", team_id: Optional[int] = None) -> Dict[str, Any]:
        """Player Info"""
        params = {}
        if team_id: params['team_id'] = team_id
        return self._make_request(f"player-info/{sport}", params)

    def get_player_stats(self, year: str, sport: str = "NBA", team_id: Optional[int] = None, player_id: Optional[int] = None) -> Dict[str, Any]:
        """Player Season Stats"""
        params = {}
        if team_id: params['team_id'] = team_id
        if player_id: params['player_id'] = player_id
        return self._make_request(f"player-stats/{year}/{sport}", params)

    def get_injuries(self, sport: str = "NBA", team_id: Optional[int] = None) -> Dict[str, Any]:
        """Injuries"""
        params = {}
        if team_id: params['team_id'] = team_id
        return self._make_request(f"injuries/{sport}", params)
        
    def get_depth_charts(self, sport: str = "NBA", team_id: Optional[int] = None) -> Dict[str, Any]:
        """Depth Charts"""
        params = {}
        if team_id: params['team_id'] = team_id
        return self._make_request(f"depth-charts/{sport}", params)

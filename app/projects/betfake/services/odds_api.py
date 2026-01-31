import requests
import os
import logging
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)

class OddsAPIService:
    BASE_URL = "https://api.the-odds-api.com/v4"
    
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("ODDS_API_KEY")
        if not self.api_key:
            logger.error("ODDS_API_KEY not found in environment variables")
        
        self.session = requests.Session()
        self.bookmakers = "draftkings,fanduel"
        self.regions = "us" # Default region
        self.odds_format = "american"

    def _get(self, endpoint, params=None):
        """Internal helper for GET requests."""
        if not self.api_key:
            return None
            
        url = f"{self.BASE_URL}/{endpoint}"
        default_params = {"apiKey": self.api_key}
        if params:
            default_params.update(params)
            
        try:
            response = self.session.get(url, params=default_params)
            response.raise_for_status()
            
            # Check remaining quota in headers
            remaining = response.headers.get('x-requests-remaining')
            if remaining:
                logger.info(f"Odds API requests remaining: {remaining}")
                
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Error calling Odds API {endpoint}: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            return None

    def fetch_sports_list(self):
        """GET /v4/sports endpoint - Returns list of active sports."""
        return self._get("sports")

    def fetch_events(self, sport_key):
        """GET /v4/sports/{sport}/events endpoint - Returns upcoming events."""
        return self._get(f"sports/{sport_key}/events")

    def fetch_odds(self, sport_key, markets="h2h,spreads,totals"):
        """GET /v4/sports/{sport}/odds endpoint - Returns events with odds."""
        params = {
            "regions": self.regions,
            "markets": markets,
            "oddsFormat": self.odds_format,
            "bookmakers": self.bookmakers
        }
        return self._get(f"sports/{sport_key}/odds", params=params)

    def fetch_scores(self, sport_key, days_from=3):
        """GET /v4/sports/{sport}/scores endpoint - Returns completed games with scores."""
        params = {
            "daysFrom": days_from
        }
        return self._get(f"sports/{sport_key}/scores", params=params)

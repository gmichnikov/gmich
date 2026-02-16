import logging
import time
from datetime import datetime, timedelta
from app.projects.sports_schedule_admin.core.espn_client import ESPNClient
from app.projects.sports_schedule_admin.core.dolthub_client import DoltHubClient

logger = logging.getLogger(__name__)

def sync_league_range(league_code, start_date, end_date):
    """
    Sync a range of dates for a given league.
    """
    espn = ESPNClient()
    dolt = DoltHubClient()
    
    current_date = start_date
    total_games_found = 0
    total_upserted = 0
    
    while current_date <= end_date:
        date_str = current_date.strftime("%Y%m%d")
        logger.info(f"Syncing {league_code} for {date_str}...")
        
        games = espn.fetch_schedule(league_code, date_str)
        if games:
            total_games_found += len(games)
            # Batch upsert to DoltHub
            # The dolt_client uses INSERT ... ON DUPLICATE KEY UPDATE
            # which prevents duplicate primary_key entries.
            result = dolt.batch_upsert("combined-schedule", games)
            
            if result and "error" not in result:
                total_upserted += len(games)
            else:
                logger.error(f"Failed to upsert games for {date_str}: {result.get('error')}")
        
        current_date += timedelta(days=1)
        # Polite delay to avoid rate limits
        # Note: DoltHub write operations also add natural delay due to polling
        time.sleep(1.0) 
    
    return {
        "league": league_code,
        "games_found": total_games_found,
        "upserted": total_upserted
    }

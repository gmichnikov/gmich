#!/usr/bin/env python3
"""
Odds API Explorer Script

This script fetches various data from The Odds API to understand response formats.
Responses are saved to the api_responses/ directory for inspection.

Toggle the flags below to control which API calls are made.
"""

import os
import json
import requests
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ============================================================================
# CONFIGURATION - Toggle these flags to enable/disable specific API calls
# ============================================================================

# Already fetched and unlikely to change:
FETCH_SPORTS_LIST = False         # Get all available sports (doesn't count against quota)

# Event lists change as games start/complete, but structure is known:
FETCH_NBA_EVENTS = False          # Get upcoming NBA games (doesn't count against quota)
FETCH_EPL_EVENTS = False          # Get upcoming EPL games (doesn't count against quota)
FETCH_NFL_EVENTS = True           # Get upcoming NFL games (doesn't count against quota)

# Fetch odds with bookmaker settings:
FETCH_NBA_ODDS = False            # Get NBA odds for h2h, spreads, totals (costs quota)
FETCH_EPL_ODDS = False            # Get EPL odds for h2h only (costs quota)
FETCH_NFL_ODDS = True             # Get NFL odds for h2h, spreads, totals (costs quota)

# Futures (only NBA has active championship futures):
FETCH_NBA_FUTURES = True          # Get NBA Championship futures (costs quota)

# Historical data - useful to get fresh completed games:
FETCH_NBA_SCORES = False          # Get recent/live NBA scores (costs quota)
FETCH_EPL_SCORES = False          # Get recent/live EPL scores (costs quota)
FETCH_NFL_SCORES = True           # Get recent/live NFL scores (costs quota)

# Sports configuration
SPORTS = {
    'nba': 'basketball_nba',
    'nba_championship': 'basketball_nba_championship_winner',
    'nfl': 'americanfootball_nfl',
    'epl': 'soccer_epl'
}

# API Configuration
API_KEY = os.getenv('ODDS_API_KEY')
BASE_URL = 'https://api.the-odds-api.com'
BOOKMAKERS = 'fanduel,draftkings'  # Limit to 1-2 major bookmakers
ODDS_FORMAT = 'american'  # american or decimal
NBA_MARKETS = 'h2h,spreads,totals'  # All markets for US sports
NFL_MARKETS = 'h2h,spreads,totals'  # All markets for US sports
EPL_MARKETS = 'h2h'  # Only h2h for soccer (limited spread/total coverage)

# Output directory
OUTPUT_DIR = Path(__file__).parent

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def ensure_output_dir():
    """Create output directory if it doesn't exist."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    print(f"📁 Saving responses to: {OUTPUT_DIR}\n")

def save_response(filename, data):
    """Save API response to JSON file."""
    filepath = OUTPUT_DIR / filename
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"✅ Saved: {filename}")

def make_request(endpoint, description):
    """Make API request and return response."""
    url = f"{BASE_URL}{endpoint}"
    print(f"🔍 Fetching: {description}")
    print(f"   URL: {url}")
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        # Show quota info from headers
        remaining = response.headers.get('x-requests-remaining', 'N/A')
        used = response.headers.get('x-requests-used', 'N/A')
        last_cost = response.headers.get('x-requests-last', 'N/A')
        
        print(f"   📊 Quota - Remaining: {remaining}, Used: {used}, Last Cost: {last_cost}")
        
        # Store quota info for final summary
        if remaining != 'N/A':
            make_request.last_remaining = remaining
            make_request.last_used = used
        
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ Error: {e}")
        return None

# Initialize storage for quota tracking
make_request.last_remaining = None
make_request.last_used = None

# ============================================================================
# API CALLS
# ============================================================================

def fetch_sports_list():
    """Fetch list of all available sports."""
    if not FETCH_SPORTS_LIST:
        return
    
    print("\n" + "="*70)
    print("FETCHING SPORTS LIST")
    print("="*70)
    
    endpoint = f"/v4/sports?apiKey={API_KEY}"
    data = make_request(endpoint, "All available sports")
    
    if data:
        save_response('sports_list.json', data)
        
        # Show NBA and EPL info if found
        print("\n📋 Looking for our target sports:")
        for sport in data:
            if sport['key'] in SPORTS.values():
                print(f"   • {sport['key']}: {sport['title']} (Active: {sport['active']})")

def fetch_events(sport_key, sport_name):
    """Fetch upcoming events for a sport."""
    endpoint = f"/v4/sports/{sport_key}/events?apiKey={API_KEY}"
    data = make_request(endpoint, f"{sport_name} upcoming events")
    
    if data:
        filename = f'events_{sport_key}.json'
        save_response(filename, data)
        print(f"   📅 Found {len(data)} upcoming events")
        if len(data) > 0:
            print(f"   Next game: {data[0]['home_team']} vs {data[0]['away_team']}")

def fetch_odds(sport_key, sport_name, markets):
    """Fetch odds for a sport (costs quota)."""
    endpoint = (f"/v4/sports/{sport_key}/odds"
                f"?apiKey={API_KEY}"
                f"&bookmakers={BOOKMAKERS}"
                f"&markets={markets}"
                f"&oddsFormat={ODDS_FORMAT}")
    
    data = make_request(endpoint, f"{sport_name} odds ({markets})")
    
    if data:
        filename = f'odds_{sport_key}.json'
        save_response(filename, data)
        print(f"   🎲 Found odds for {len(data)} events")
        if len(data) > 0:
            num_bookmakers = len(data[0].get('bookmakers', []))
            print(f"   First event has {num_bookmakers} bookmakers")

def fetch_futures(sport_key, sport_name):
    """Fetch futures/outrights for a sport (costs quota)."""
    # Futures use the standard odds endpoint but with a dedicated sport key
    endpoint = (f"/v4/sports/{sport_key}/odds"
                f"?apiKey={API_KEY}"
                f"&bookmakers={BOOKMAKERS}"
                f"&oddsFormat={ODDS_FORMAT}")
    
    data = make_request(endpoint, f"{sport_name} futures/outrights")
    
    if data:
        filename = f'futures_{sport_key}.json'
        save_response(filename, data)
        print(f"   🏆 Found {len(data)} future market events")
        if len(data) > 0:
            num_bookmakers = len(data[0].get('bookmakers', []))
            print(f"   First market has {num_bookmakers} bookmakers")

def fetch_scores(sport_key, sport_name):
    """Fetch recent/live scores for a sport (costs quota)."""
    endpoint = (f"/v4/sports/{sport_key}/scores"
                f"?apiKey={API_KEY}"
                f"&daysFrom=3")  # Include games from last 3 days
    
    data = make_request(endpoint, f"{sport_name} recent scores")
    
    if data:
        filename = f'scores_{sport_key}.json'
        save_response(filename, data)
        
        completed = [g for g in data if g.get('completed', False)]
        live = [g for g in data if not g.get('completed', False) and 
                datetime.fromisoformat(g['commence_time'].replace('Z', '+00:00')) < datetime.now(datetime.fromisoformat(g['commence_time'].replace('Z', '+00:00')).tzinfo)]
        
        print(f"   🏆 Found {len(completed)} completed games, {len(live)} live/upcoming")

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution flow."""
    print("\n" + "="*70)
    print("ODDS API EXPLORER")
    print("="*70)
    
    if not API_KEY:
        print("❌ ERROR: ODDS_API_KEY not found in environment variables")
        print("   Add it to your .env file: ODDS_API_KEY=your_key_here")
        return
    
    print(f"✓ API Key found: {API_KEY[:10]}...")
    
    ensure_output_dir()
    
    # Fetch sports list first
    fetch_sports_list()
    
    # NBA
    if FETCH_NBA_EVENTS or FETCH_NBA_ODDS or FETCH_NBA_FUTURES or FETCH_NBA_SCORES:
        print("\n" + "="*70)
        print("NBA (National Basketball Association)")
        print("="*70)
        
        if FETCH_NBA_EVENTS:
            fetch_events(SPORTS['nba'], 'NBA')
        
        if FETCH_NBA_ODDS:
            print()
            fetch_odds(SPORTS['nba'], 'NBA', NBA_MARKETS)
        
        if FETCH_NBA_FUTURES:
            print()
            fetch_futures(SPORTS['nba_championship'], 'NBA Championship')
        
        if FETCH_NBA_SCORES:
            print()
            fetch_scores(SPORTS['nba'], 'NBA')
    
    # EPL
    if FETCH_EPL_EVENTS or FETCH_EPL_ODDS or FETCH_EPL_SCORES:
        print("\n" + "="*70)
        print("EPL (English Premier League)")
        print("="*70)
        
        if FETCH_EPL_EVENTS:
            fetch_events(SPORTS['epl'], 'EPL')
        
        if FETCH_EPL_ODDS:
            print()
            fetch_odds(SPORTS['epl'], 'EPL', EPL_MARKETS)
        
        if FETCH_EPL_SCORES:
            print()
            fetch_scores(SPORTS['epl'], 'EPL')
    
    # NFL
    if FETCH_NFL_EVENTS or FETCH_NFL_ODDS or FETCH_NFL_SCORES:
        print("\n" + "="*70)
        print("NFL (National Football League)")
        print("="*70)
        
        if FETCH_NFL_EVENTS:
            fetch_events(SPORTS['nfl'], 'NFL')
        
        if FETCH_NFL_ODDS:
            print()
            fetch_odds(SPORTS['nfl'], 'NFL', NFL_MARKETS)
        
        if FETCH_NFL_SCORES:
            print()
            fetch_scores(SPORTS['nfl'], 'NFL')
    
    print("\n" + "="*70)
    print("✅ COMPLETE - Check the api_responses/ folder for JSON files")
    print("="*70)
    
    # Display final quota summary
    if make_request.last_remaining is not None:
        print(f"\n📊 FINAL QUOTA STATUS:")
        print(f"   Credits Remaining: {make_request.last_remaining}")
        print(f"   Credits Used (this period): {make_request.last_used}")
    
    print("\n⚠️  NOTE: Running this script again will OVERWRITE existing JSON files.")
    print("   If you want to keep old data, rename files before re-running.")
    print()

if __name__ == '__main__':
    main()

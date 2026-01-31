import click
from flask.cli import with_appcontext
from app.projects.betfake.services.data_import import DataImportService
from app.projects.betfake.services.bet_grader import BetGraderService
import logging

logger = logging.getLogger(__name__)

@click.group(name='betfake')
def betfake_cli():
    """BetFake project commands."""
    pass

@betfake_cli.command('sync')
@click.option('--sport', default=None, help='Specific sport key to sync (e.g. basketball_nba)')
@with_appcontext
def sync_command(sport):
    """Sync games, odds, and scores from the Odds API."""
    importer = DataImportService()
    grader = BetGraderService()
    
    sports_to_sync = []
    if sport:
        sports_to_sync.append(sport)
    else:
        # Default sports for V1
        sports_to_sync = ['basketball_nba', 'americanfootball_nfl', 'soccer_epl']
    
    for sport_key in sports_to_sync:
        click.echo(f"Syncing {sport_key}...")
        
        # 1. Sync Games
        game_count = importer.import_games_for_sport(sport_key)
        click.echo(f"  - Imported/Updated {game_count} games")
        
        # 2. Sync Odds
        markets = "h2h,spreads,totals"
        if sport_key == 'soccer_epl':
            markets = "h2h"
            
        market_count = importer.import_odds_for_sport(sport_key, markets_str=markets)
        click.echo(f"  - Imported {market_count} markets")
        
        # 3. Sync Scores
        score_count = importer.import_scores_for_sport(sport_key)
        click.echo(f"  - Updated {score_count} completed games with scores")
        
        # 4. Sync Futures (only for NBA in V1)
        if sport_key == 'basketball_nba':
            click.echo(f"  - Syncing NBA Futures...")
            futures_count = importer.import_futures('basketball_nba_championship_winner')
            click.echo(f"    - Imported {futures_count} futures markets")

    # 5. Settle Bets
    click.echo("Settling pending bets...")
    settled_count = grader.settle_pending_bets()
    click.echo(f"Settle complete! {settled_count} bets settled.")
    click.echo("Sync complete!")

@betfake_cli.command('settle')
@click.option('--game-id', default=None, type=int, help='Settle bets for a specific game ID')
@with_appcontext
def settle_command(game_id):
    """Manually trigger bet settlement for completed games."""
    grader = BetGraderService()
    settled_count = grader.settle_pending_bets(game_id=game_id)
    click.echo(f"Settled {settled_count} bets.")

def init_app(app):
    """Register CLI commands with the app."""
    app.cli.add_command(betfake_cli)

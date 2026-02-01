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

@betfake_cli.command('sync-scores')
@click.option('--sport', default=None, help='Specific sport key to sync (e.g. basketball_nba)')
@with_appcontext
def sync_scores_command(sport):
    """Sync scores only and settle bets."""
    importer = DataImportService()
    grader = BetGraderService()
    from app.models import LogEntry
    from app.projects.betfake.models import BetfakeSport
    from app import db
    
    if sport:
        sports_to_sync = BetfakeSport.query.filter_by(sport_key=sport).all()
    else:
        sports_to_sync = BetfakeSport.query.filter_by(sync_scores=True).all()
    
    if not sports_to_sync:
        click.echo("No sports enabled for score sync.")
        return

    for s_obj in sports_to_sync:
        sport_key = s_obj.sport_key
        click.echo(f"Syncing scores for {s_obj.sport_title}...")
        score_count = importer.import_scores_for_sport(sport_key)
        quota = importer.api.last_remaining_quota
        
        log_desc = f"Sync Scores: {s_obj.sport_title} updated {score_count} games."
        if quota: log_desc += f" API Quota remaining: {quota}"
        
        db.session.add(LogEntry(project='betfake', category='Sync Step', description=log_desc))
        db.session.commit()
        click.echo(f"  - Updated {score_count} games. Quota: {quota}")

    click.echo("Settling pending bets...")
    settled_count = grader.settle_pending_bets()
    db.session.add(LogEntry(project='betfake', category='Settlement', description=f"Settled {settled_count} bets after score sync."))
    db.session.commit()
    click.echo(f"Settle complete! {settled_count} bets settled.")

@betfake_cli.command('sync-odds')
@click.option('--sport', default=None, help='Specific sport key to sync (e.g. basketball_nba)')
@with_appcontext
def sync_odds_command(sport):
    """Sync upcoming games and odds only."""
    importer = DataImportService()
    from app.models import LogEntry
    from app.projects.betfake.models import BetfakeSport
    from app import db
    
    if sport:
        sports_to_sync = BetfakeSport.query.filter_by(sport_key=sport).all()
    else:
        sports_to_sync = BetfakeSport.query.filter_by(sync_odds=True).all()

    if not sports_to_sync:
        click.echo("No sports enabled for odds sync.")
        return
    
    for s_obj in sports_to_sync:
        sport_key = s_obj.sport_key
        click.echo(f"Syncing odds for {s_obj.sport_title}...")
        
        # 1. Games
        game_count = importer.import_games_for_sport(sport_key)
        
        # 2. Odds
        markets = "h2h,spreads,totals" if s_obj.has_spreads else "h2h"
        
        # Check if it's a futures sport (outright)
        if s_obj.is_outright:
            click.echo(f"  - Syncing Outrights for {s_obj.sport_title}...")
            market_count = importer.import_futures(sport_key)
        else:
            market_count = importer.import_odds_for_sport(sport_key, markets_str=markets)
            
        odds_quota = importer.api.last_remaining_quota
        
        log_desc = f"Sync Odds: {s_obj.sport_title} imported {game_count} games, {market_count} markets."
        if odds_quota: log_desc += f" API Quota remaining: {odds_quota}"
        
        db.session.add(LogEntry(project='betfake', category='Sync Step', description=log_desc))
        db.session.commit()
        click.echo(f"  - {game_count} games, {market_count} markets. Quota: {odds_quota}")

@betfake_cli.command('sync')
@click.option('--sport', default=None, help='Specific sport key to sync (e.g. basketball_nba)')
@click.pass_context
@with_appcontext
def sync_command(ctx, sport):
    """Full sync: scores, then odds."""
    click.echo("Starting Full Sync...")
    ctx.invoke(sync_scores_command, sport=sport)
    ctx.invoke(sync_odds_command, sport=sport)
    click.echo("Full Sync complete!")

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

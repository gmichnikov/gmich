from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from datetime import datetime
import logging

from app.projects.betfake.models import (
    BetfakeAccount, BetfakeBet, BetfakeTransaction, 
    TransactionType, db, GameStatus, BetfakeGame, 
    BetfakeMarket, MarketType, BetfakeOutcome, BetStatus
)
from app.models import User
from app.core.admin import admin_required
from app.projects.betfake.services.data_import import DataImportService
from app.projects.betfake.utils import format_odds_display, format_currency, get_user_localized_time

betfake_bp = Blueprint(
    'betfake', 
    __name__,
    template_folder='templates',
    static_folder='static'
)

@betfake_bp.app_template_filter('bf_odds')
def bf_odds_filter(odds):
    return format_odds_display(odds)

@betfake_bp.app_template_filter('bf_currency')
def bf_currency_filter(amount):
    return format_currency(amount)

@betfake_bp.app_template_filter('bf_local_time')
def bf_local_time_filter(utc_dt):
    user_tz = current_user.time_zone if current_user.is_authenticated else 'UTC'
    return get_user_localized_time(utc_dt, user_tz)

@betfake_bp.route('/')
@login_required
def index():
    """Dashboard showing accounts and recent bets."""
    accounts = BetfakeAccount.query.filter_by(user_id=current_user.id).order_by(BetfakeAccount.created_at).all()
    
    # If no accounts, we'll show a prompt to create one in the template
    
    pending_bets = BetfakeBet.query.filter_by(user_id=current_user.id, status='Pending').order_by(BetfakeBet.placed_at.desc()).all()
    
    # Calculate total balance across accounts
    total_balance = sum(account.balance for account in accounts)
    
    # Calculate total profit/loss (Won - Lost)
    # This will be more accurate once we have settled bets
    settled_bets = BetfakeBet.query.filter(
        BetfakeBet.user_id == current_user.id,
        BetfakeBet.status.in_(['Won', 'Lost'])
    ).all()
    
    total_pl = 0
    for bet in settled_bets:
        if bet.status.value == 'Won':
            total_pl += (bet.potential_payout - bet.wager_amount)
        elif bet.status.value == 'Lost':
            total_pl -= bet.wager_amount
            
    # Format PL for display
    formatted_total_pl = format_currency(total_pl)
    if total_pl > 0:
        formatted_total_pl = "+" + formatted_total_pl
            
    return render_template('betfake/index.html', 
                           accounts=accounts, 
                           pending_bets=pending_bets,
                           total_balance=total_balance,
                           total_pl=total_pl,
                           formatted_total_pl=formatted_total_pl)

@betfake_bp.route('/accounts/create', methods=['POST'])
@login_required
def create_account():
    """Create a new betting account with initial $100 balance."""
    account_name = request.form.get('name', '').strip()
    
    if not account_name:
        flash('Account name is required.', 'error')
        return redirect(url_for('betfake.index'))
    
    new_account = BetfakeAccount(
        user_id=current_user.id,
        name=account_name,
        balance=100.0
    )
    db.session.add(new_account)
    db.session.flush() # Get the ID
    
    # Create transaction record
    transaction = BetfakeTransaction(
        user_id=current_user.id,
        account_id=new_account.id,
        amount=100.0,
        type=TransactionType.Account_Creation
    )
    db.session.add(transaction)
    
    try:
        db.session.commit()
        flash(f'Account "{account_name}" created successfully with $100.00 balance!', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error creating betfake account: {str(e)}")
        flash('An error occurred while creating the account.', 'error')
        
    return redirect(url_for('betfake.index'))

@betfake_bp.route('/sports/<sport_key>')
@login_required
def browse_sport(sport_key):
    """Browse games for a specific sport with bookmaker fallback logic."""
    # Query active games for sport (Scheduled, not yet started)
    now = datetime.utcnow()
    games = BetfakeGame.query.filter(
        BetfakeGame.sport_key == sport_key,
        BetfakeGame.status == GameStatus.Scheduled,
        BetfakeGame.commence_time > now
    ).order_by(BetfakeGame.commence_time.asc()).all()
    
    # For each game, select the "Best Available" market of each type
    for game in games:
        game.display_markets = {}
        
        # We support h2h, spreads, totals for V1 (soccer only h2h)
        market_types = [MarketType.h2h]
        if sport_key != 'soccer_epl':
            market_types.extend([MarketType.spreads, MarketType.totals])
            
        for mt in market_types:
            # 1. Try DraftKings (Primary)
            market = BetfakeMarket.query.filter_by(
                game_id=game.id,
                type=mt,
                bookmaker_key='draftkings',
                is_active=True
            ).first()
            
            # 2. Fallback to FanDuel
            if not market:
                market = BetfakeMarket.query.filter_by(
                    game_id=game.id,
                    type=mt,
                    bookmaker_key='fanduel',
                    is_active=True
                ).first()
            
            if market:
                game.display_markets[mt.value] = market

    return render_template('betfake/sports.html', 
                           sport_key=sport_key, 
                           games=games,
                           now=now)

@betfake_bp.route('/bet/<int:outcome_id>')
@login_required
def bet_page(outcome_id):
    """Bet placement page for a specific outcome."""
    outcome = BetfakeOutcome.query.get_or_404(outcome_id)
    if not outcome.is_active or not outcome.market.is_active:
        flash("This line is no longer active. Please select a new one.", "error")
        return redirect(url_for('betfake.browse_sport', sport_key=outcome.market.game.sport_key))
    
    game = outcome.market.game
    now = datetime.utcnow()
    if game.commence_time < now:
        flash("Betting has closed for this game.", "error")
        return redirect(url_for('betfake.browse_sport', sport_key=game.sport_key))
    
    accounts = BetfakeAccount.query.filter_by(user_id=current_user.id).all()
    if not accounts:
        flash("You need to create a betting account first!", "warning")
        return redirect(url_for('betfake.index'))
        
    return render_template('betfake/bet.html', 
                           outcome=outcome, 
                           game=game, 
                           accounts=accounts)

@betfake_bp.route('/bet/<int:outcome_id>/place', methods=['POST'])
@login_required
def place_bet(outcome_id):
    """Process bet placement."""
    from app.projects.betfake.utils import calculate_american_odds_payout
    
    outcome = BetfakeOutcome.query.get_or_404(outcome_id)
    
    # 1. Validation
    if not outcome.is_active or not outcome.market.is_active:
        flash("This line is no longer active. Please select a new one.", "error")
        return redirect(url_for('betfake.browse_sport', sport_key=outcome.market.game.sport_key))
        
    game = outcome.market.game
    if game.commence_time < datetime.utcnow():
        flash("Betting has closed for this game.", "error")
        return redirect(url_for('betfake.browse_sport', sport_key=game.sport_key))
        
    account_id = request.form.get('account_id')
    account = BetfakeAccount.query.get_or_404(account_id)
    if account.user_id != current_user.id:
        flash("Unauthorized account.", "error")
        return redirect(url_for('betfake.index'))
        
    try:
        wager_amount = float(request.form.get('wager_amount', 0))
        if wager_amount <= 0:
            flash("Wager amount must be greater than zero.", "error")
            return redirect(url_for('betfake.bet_page', outcome_id=outcome_id))
        
        # Check precision
        if round(wager_amount, 2) != wager_amount:
            flash("Wager amount cannot have more than 2 decimal places.", "error")
            return redirect(url_for('betfake.bet_page', outcome_id=outcome_id))
            
        if wager_amount > account.balance:
            flash(f"Insufficient balance in {account.name}.", "error")
            return redirect(url_for('betfake.bet_page', outcome_id=outcome_id))
            
    except ValueError:
        flash("Invalid wager amount.", "error")
        return redirect(url_for('betfake.bet_page', outcome_id=outcome_id))

    # 2. Placement Logic
    potential_payout = calculate_american_odds_payout(wager_amount, outcome.odds)
    
    bet = BetfakeBet(
        user_id=current_user.id,
        account_id=account.id,
        outcome_id=outcome.id,
        wager_amount=wager_amount,
        odds_at_time=outcome.odds,
        line_at_time=outcome.point_value,
        outcome_name_at_time=outcome.outcome_name,
        potential_payout=potential_payout,
        status=BetStatus.Pending
    )
    
    # Deduct balance
    account.balance -= wager_amount
    
    # Create transaction
    transaction = BetfakeTransaction(
        user_id=current_user.id,
        account_id=account.id,
        amount=-wager_amount,
        type=TransactionType.Wager
    )
    
    db.session.add(bet)
    db.session.add(transaction)
    
    try:
        db.session.commit()
        # Link transaction to bet after commit to get bet.id
        transaction.bet_id = bet.id
        db.session.commit()
        flash("Bet placed successfully!", "success")
    except Exception as e:
        db.session.rollback()
        logging.error(f"Bet placement error: {str(e)}")
        flash("An error occurred while placing your bet.", "error")
        
    return redirect(url_for('betfake.index'))

@betfake_bp.route('/futures')
@login_required
def futures():
    """Browse futures markets grouped by sport."""
    # Query all active futures markets
    # Futures games have home_team=None and away_team=None
    futures_games = BetfakeGame.query.filter(
        BetfakeGame.home_team == None,
        BetfakeGame.away_team == None,
        BetfakeGame.status == GameStatus.Scheduled
    ).all()
    
    # Organize by sport
    organized_futures = {}
    for game in futures_games:
        # Get the outrights market for this game
        market = BetfakeMarket.query.filter_by(
            game_id=game.id,
            type=MarketType.outrights,
            is_active=True
        ).first()
        
        if market:
            sport_title = game.sport_title
            if sport_title not in organized_futures:
                organized_futures[sport_title] = []
            
            # Sort outcomes by odds (favorites first)
            sorted_outcomes = sorted(market.outcomes, key=lambda x: x.odds)
            
            organized_futures[sport_title].append({
                'label': game.sport_title,
                'end_date': game.commence_time,
                'outcomes': sorted_outcomes
            })
            
    return render_template('betfake/futures.html', organized_futures=organized_futures)


@betfake_bp.route('/history')
@login_required
def history():
    """View full bet history."""
    # Query all bets for user, joined with necessary info
    bets = BetfakeBet.query.filter_by(user_id=current_user.id).order_by(BetfakeBet.placed_at.desc()).all()
    
    # Summary stats
    stats = {
        'total_wagered': sum(b.wager_amount for b in bets),
        'total_payout': sum(b.potential_payout for b in bets if b.status.value == 'Won'),
        'wins': len([b for b in bets if b.status.value == 'Won']),
        'losses': len([b for b in bets if b.status.value == 'Lost']),
        'pushes': len([b for b in bets if b.status.value == 'Push']),
        'pending': len([b for b in bets if b.status.value == 'Pending'])
    }
    
    return render_template('betfake/history.html', bets=bets, stats=stats)

@betfake_bp.route('/transactions/<int:account_id>')
@login_required
def transactions(account_id):
    """View transactions for a specific account."""
    account = BetfakeAccount.query.get_or_404(account_id)
    if account.user_id != current_user.id:
        flash("Unauthorized account.", "error")
        return redirect(url_for('betfake.index'))
        
    transactions = BetfakeTransaction.query.filter_by(account_id=account.id).order_by(BetfakeTransaction.created_at.desc()).all()
    
    return render_template('betfake/transactions.html', account=account, transactions=transactions)


@betfake_bp.route('/admin/sync')
@login_required
@admin_required
def admin_sync():
    """Admin page to manually trigger Odds API sync."""
    return render_template('betfake/admin_sync.html')

@betfake_bp.route('/admin/sync/trigger', methods=['POST'])
@login_required
@admin_required
def admin_sync_trigger():
    """Route to trigger the sync process."""
    sport = request.form.get('sport')
    importer = DataImportService()
    
    try:
        if sport:
            importer.import_games_for_sport(sport)
            # For sport-specific sync, we need to know which markets to sync
            markets = "h2h,spreads,totals"
            if sport == 'soccer_epl':
                markets = "h2h"
            importer.import_odds_for_sport(sport, markets_str=markets)
            importer.import_scores_for_sport(sport)
            if sport == 'basketball_nba':
                importer.import_futures('basketball_nba_championship_winner')
            flash(f"Successfully synced {sport}.", "success")
        else:
            # Full sync
            for s in ['basketball_nba', 'americanfootball_nfl', 'soccer_epl']:
                importer.import_games_for_sport(s)
                markets = "h2h,spreads,totals"
                if s == 'soccer_epl':
                    markets = "h2h"
                importer.import_odds_for_sport(s, markets_str=markets)
                importer.import_scores_for_sport(s)
            importer.import_futures('basketball_nba_championship_winner')
            flash("Full sync completed successfully.", "success")
    except Exception as e:
        logging.error(f"Sync error: {str(e)}")
        flash(f"Error during sync: {str(e)}", "error")
        
    return redirect(url_for('betfake.admin_sync'))

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.projects.betfake.models import BetfakeAccount, BetfakeBet, BetfakeTransaction, TransactionType, db
from app.models import User
import logging

betfake_bp = Blueprint(
    'betfake', 
    __name__,
    template_folder='templates',
    static_folder='static'
)

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
            
    return render_template('betfake/index.html', 
                           accounts=accounts, 
                           pending_bets=pending_bets,
                           total_balance=total_balance,
                           total_pl=total_pl)

@betfake_bp.route('/accounts/create', methods=['POST'])
@login_required
def create_account():
    """Create a new betting account with initial $100 balance."""
    account_name = request.form.get('name', '').strip()
    
    if not account_name:
        flash('Account name is required.', 'error')
        return redirect(url_for('betfake.index'))
    
    # Optional: Limit number of accounts? User said "Don't worry about account creation limits"
    
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
    """Browse games for a specific sport."""
    # Placeholder for Phase 2
    return render_template('betfake/sports.html', sport_key=sport_key)

@betfake_bp.route('/futures')
@login_required
def futures():
    """Browse futures markets."""
    # Placeholder for Phase 2/5
    return render_template('betfake/futures.html')

@betfake_bp.route('/history')
@login_required
def history():
    """View full bet history."""
    # Placeholder for Phase 3
    return render_template('betfake/history.html')

@betfake_bp.route('/transactions/<int:account_id>')
@login_required
def transactions(account_id):
    """View transactions for a specific account."""
    # Placeholder for Phase 3.4
    return render_template('betfake/transactions.html', account_id=account_id)

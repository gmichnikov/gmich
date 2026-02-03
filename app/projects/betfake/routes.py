from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from datetime import datetime
import logging

from app.projects.betfake.models import (
    BetfakeAccount,
    BetfakeBet,
    BetfakeTransaction,
    TransactionType,
    db,
    GameStatus,
    BetfakeGame,
    BetfakeMarket,
    MarketType,
    BetfakeOutcome,
    BetStatus,
)
from app.models import User
from app.core.admin import admin_required
from app.projects.betfake.services.data_import import DataImportService
from app.projects.betfake.utils import (
    format_odds_display,
    format_currency,
    get_user_localized_time,
)
from app.models import User, LogEntry

betfake_bp = Blueprint(
    "betfake", __name__, template_folder="templates", static_folder="static"
)


@betfake_bp.app_context_processor
def inject_active_sports():
    """Inject active sports into all betfake templates for navigation."""
    from app.projects.betfake.models import BetfakeSport

    # Get sports marked for navigation, but exclude futures/outrights from the top bar
    active_sports = (
        BetfakeSport.query.filter_by(show_in_nav=True, is_outright=False)
        .order_by(BetfakeSport.sport_title)
        .all()
    )
    return dict(active_sports=active_sports)


@betfake_bp.app_template_filter("bf_odds")
def bf_odds_filter(odds):
    return format_odds_display(odds)


@betfake_bp.app_template_filter("bf_currency")
def bf_currency_filter(amount):
    return format_currency(amount)


@betfake_bp.app_template_filter("bf_local_time")
def bf_local_time_filter(utc_dt):
    user_tz = current_user.time_zone if current_user.is_authenticated else "UTC"
    return get_user_localized_time(utc_dt, user_tz)


@betfake_bp.app_template_filter("bf_point")
def bf_point_filter(point):
    if point is None:
        return ""
    return f"{point:+g}"


@betfake_bp.app_template_filter("bf_bet_outcome")
def bf_bet_outcome_filter(bet):
    market_type = bet.outcome.market.type
    outcome_name = bet.outcome_name_at_time
    line = bet.line_at_time

    if market_type == MarketType.h2h:
        if outcome_name == "Draw":
            return "Draw"
        return f"{outcome_name} to win"
    elif market_type == MarketType.spreads:
        line_str = f"{line:+g}" if line is not None else ""
        return f"{outcome_name} {line_str}"
    elif market_type == MarketType.totals:
        return f"{outcome_name} {line}"
    return outcome_name


@betfake_bp.route("/")
@login_required
def index():
    """Dashboard showing accounts and recent bets."""
    from app.projects.betfake.models import BetfakeSport

    accounts = (
        BetfakeAccount.query.filter_by(user_id=current_user.id)
        .order_by(BetfakeAccount.created_at)
        .all()
    )

    pending_bets = (
        BetfakeBet.query.filter_by(user_id=current_user.id, status="Pending")
        .order_by(BetfakeBet.placed_at.desc())
        .all()
    )

    # Calculate total balance across accounts
    total_balance = sum(account.balance for account in accounts)

    # Calculate total pending wagers for equity
    total_pending_wagers = sum(bet.wager_amount for bet in pending_bets)
    total_equity = total_balance + total_pending_wagers

    # Calculate total profit/loss (Won - Lost)
    # This will be more accurate once we have settled bets
    settled_bets = BetfakeBet.query.filter(
        BetfakeBet.user_id == current_user.id,
        BetfakeBet.status.in_(["Won", "Lost", "Push"]),
    ).all()

    total_pl = 0
    # Dictionary to track P/L per account
    account_pls = {account.id: 0 for account in accounts}

    for bet in settled_bets:
        bet_pl = 0
        if bet.status.value == "Won":
            bet_pl = bet.potential_payout - bet.wager_amount
        elif bet.status.value == "Lost":
            bet_pl = -bet.wager_amount

        total_pl += bet_pl
        if bet.account_id in account_pls:
            account_pls[bet.account_id] += bet_pl

    # Format PL for display
    formatted_total_pl = format_currency(total_pl)
    if total_pl > 0:
        formatted_total_pl = "+" + formatted_total_pl

    # Format account PLs for display
    formatted_account_pls = {}
    for acc_id, pl in account_pls.items():
        fmt = format_currency(pl)
        if pl > 0:
            fmt = "+" + fmt
        formatted_account_pls[acc_id] = {"raw": pl, "formatted": fmt}

    recent_settled = (
        BetfakeBet.query.filter(
            BetfakeBet.user_id == current_user.id,
            BetfakeBet.status.in_(["Won", "Lost", "Push"]),
        )
        .order_by(BetfakeBet.settled_at.desc())
        .limit(3)
        .all()
    )

    # Get the first active sport for the "Browse" button
    first_sport = (
        BetfakeSport.query.filter_by(show_in_nav=True)
        .order_by(BetfakeSport.sport_title)
        .first()
    )

    return render_template(
        "betfake/index.html",
        accounts=accounts,
        pending_bets=pending_bets,
        total_balance=total_balance,
        total_equity=total_equity,
        total_pl=total_pl,
        formatted_total_pl=formatted_total_pl,
        account_pls=formatted_account_pls,
        recent_settled=recent_settled,
        first_sport=first_sport,
    )


@betfake_bp.route("/accounts/create", methods=["POST"])
@login_required
def create_account():
    """Create a new betting account with initial $100 balance."""
    account_name = request.form.get("name", "").strip()

    if not account_name:
        flash("Account name is required.", "error")
        return redirect(url_for("betfake.index"))

    new_account = BetfakeAccount(
        user_id=current_user.id, name=account_name, balance=100.0
    )
    db.session.add(new_account)
    db.session.flush()  # Get the ID

    # Log the account creation
    log_entry = LogEntry(
        project="betfake",
        category="Account",
        actor_id=current_user.id,
        description=f"{current_user.email} created BetFake account '{account_name}'",
    )
    db.session.add(log_entry)

    # Create transaction record
    transaction = BetfakeTransaction(
        user_id=current_user.id,
        account_id=new_account.id,
        amount=100.0,
        type=TransactionType.Account_Creation,
    )
    db.session.add(transaction)

    try:
        db.session.commit()
        flash(
            f'Account "{account_name}" created successfully with $100.00 balance!',
            "success",
        )
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error creating betfake account: {str(e)}")
        flash("An error occurred while creating the account.", "error")

    return redirect(url_for("betfake.index"))


@betfake_bp.route("/sports/<sport_key>")
@login_required
def browse_sport(sport_key):
    """Browse games for a specific sport with upcoming and recent sections."""
    from datetime import timedelta
    from app.projects.betfake.models import BetfakeSport

    # Get sport details from registry
    sport = BetfakeSport.query.filter_by(sport_key=sport_key).first()
    if not sport:
        flash(f"Sport {sport_key} not found.", "error")
        return redirect(url_for("betfake.index"))

    now = datetime.utcnow()
    recent_cutoff = now - timedelta(hours=48)
    seven_days_ago = now - timedelta(days=7)

    # 1. Upcoming Games (Scheduled, not yet started)
    upcoming_games = (
        BetfakeGame.query.filter(
            BetfakeGame.sport_key == sport_key,
            BetfakeGame.status == GameStatus.Scheduled,
            BetfakeGame.commence_time > now,
        )
        .order_by(BetfakeGame.commence_time.asc())
        .all()
    )

    # For each upcoming game, select the "Best Available" market
    for game in upcoming_games:
        game.display_markets = {}
        market_types = [MarketType.h2h]

        # Use has_spreads flag from DB
        if sport.has_spreads:
            market_types.extend([MarketType.spreads, MarketType.totals])

        for mt in market_types:
            market = BetfakeMarket.query.filter_by(
                game_id=game.id, type=mt, bookmaker_key="draftkings", is_active=True
            ).first()
            if not market:
                market = BetfakeMarket.query.filter_by(
                    game_id=game.id, type=mt, bookmaker_key="fanduel", is_active=True
                ).first()
            if market:
                game.display_markets[mt.value] = market

    # 2. Recent Games (Last 48h OR (Last 7d AND user bet))
    # ... (same logic as before) ...
    recent_candidates = BetfakeGame.query.filter(
        BetfakeGame.sport_key == sport_key,
        BetfakeGame.commence_time >= seven_days_ago,
        BetfakeGame.commence_time <= now,
    ).all()

    # Get IDs of games the user bet on
    user_bet_game_ids = [
        r[0]
        for r in db.session.query(BetfakeMarket.game_id)
        .join(BetfakeOutcome)
        .join(BetfakeBet)
        .filter(BetfakeBet.user_id == current_user.id)
        .distinct()
        .all()
    ]

    recent_games = []
    for game in recent_candidates:
        is_recent = game.commence_time >= recent_cutoff
        has_user_bet = game.id in user_bet_game_ids
        if is_recent or has_user_bet:
            recent_games.append(game)

    recent_games.sort(key=lambda x: x.commence_time, reverse=True)

    return render_template(
        "betfake/sports.html",
        sport_key=sport_key,
        sport_label=sport.display_title,  # Use title from DB (preferred if exists)
        upcoming_games=upcoming_games,
        recent_games=recent_games,
        now=now,
        has_spreads=sport.has_spreads,
    )  # Pass flag to template


@betfake_bp.route("/bet/<int:outcome_id>")
@login_required
def bet_page(outcome_id):
    """Bet placement page for a specific outcome."""
    outcome = BetfakeOutcome.query.get_or_404(outcome_id)
    if not outcome.is_active or not outcome.market.is_active:
        flash("This line is no longer active. Please select a new one.", "error")
        return redirect(
            url_for("betfake.browse_sport", sport_key=outcome.market.game.sport_key)
        )

    game = outcome.market.game
    now = datetime.utcnow()
    if game.commence_time < now:
        flash("Betting has closed for this game.", "error")
        return redirect(url_for("betfake.browse_sport", sport_key=game.sport_key))

    accounts = BetfakeAccount.query.filter_by(user_id=current_user.id).all()
    if not accounts:
        flash("You need to create a betting account first!", "warning")
        return redirect(url_for("betfake.index"))

    return render_template(
        "betfake/bet.html", outcome=outcome, game=game, accounts=accounts
    )


@betfake_bp.route("/bet/<int:outcome_id>/place", methods=["POST"])
@login_required
def place_bet(outcome_id):
    """Process bet placement."""
    from app.projects.betfake.utils import calculate_american_odds_payout

    outcome = BetfakeOutcome.query.get_or_404(outcome_id)

    # 1. Validation
    if not outcome.is_active or not outcome.market.is_active:
        flash("This line is no longer active. Please select a new one.", "error")
        return redirect(
            url_for("betfake.browse_sport", sport_key=outcome.market.game.sport_key)
        )

    game = outcome.market.game
    if game.commence_time < datetime.utcnow():
        flash("Betting has closed for this game.", "error")
        return redirect(url_for("betfake.browse_sport", sport_key=game.sport_key))

    account_id = request.form.get("account_id")
    account = BetfakeAccount.query.get_or_404(account_id)
    if account.user_id != current_user.id:
        flash("Unauthorized account.", "error")
        return redirect(url_for("betfake.index"))

    try:
        wager_amount = float(request.form.get("wager_amount", 0))
        if wager_amount <= 0:
            flash("Wager amount must be greater than zero.", "error")
            return redirect(url_for("betfake.bet_page", outcome_id=outcome_id))

        # Check precision
        if round(wager_amount, 2) != wager_amount:
            flash("Wager amount cannot have more than 2 decimal places.", "error")
            return redirect(url_for("betfake.bet_page", outcome_id=outcome_id))

        if wager_amount > account.balance:
            flash(f"Insufficient balance in {account.name}.", "error")
            return redirect(url_for("betfake.bet_page", outcome_id=outcome_id))

    except ValueError:
        flash("Invalid wager amount.", "error")
        return redirect(url_for("betfake.bet_page", outcome_id=outcome_id))

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
        status=BetStatus.Pending,
    )

    # Deduct balance
    account.balance -= wager_amount

    # Create transaction
    transaction = BetfakeTransaction(
        user_id=current_user.id,
        account_id=account.id,
        amount=-wager_amount,
        type=TransactionType.Wager,
    )

    db.session.add(bet)
    db.session.add(transaction)

    # Log the bet placement
    matchup = (
        f"{game.away_team} @ {game.home_team}"
        if game.home_team
        else game.display_sport_title
    )
    odds_str = f"+{bet.odds_at_time}" if bet.odds_at_time > 0 else str(bet.odds_at_time)
    log_entry = LogEntry(
        project="betfake",
        category="Bet",
        actor_id=current_user.id,
        description=f"{current_user.email} wagered ${wager_amount:,.2f} on {bet.outcome_name_at_time} in {matchup} ({odds_str})",
    )
    db.session.add(log_entry)

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

    return redirect(url_for("betfake.index"))


@betfake_bp.route("/futures")
@login_required
def futures():
    """Browse futures markets grouped by sport."""
    # Query all active futures markets
    # Futures games have home_team=None and away_team=None
    futures_games = BetfakeGame.query.filter(
        BetfakeGame.home_team == None,
        BetfakeGame.away_team == None,
        BetfakeGame.status == GameStatus.Scheduled,
    ).all()

    # Organize by sport
    organized_futures = {}
    for game in futures_games:
        # Get the outrights market for this game
        market = BetfakeMarket.query.filter_by(
            game_id=game.id, type=MarketType.outrights, is_active=True
        ).first()

        if market:
            sport_title = game.display_sport_title
            if sport_title not in organized_futures:
                organized_futures[sport_title] = []

            # Sort outcomes by odds (favorites first)
            sorted_outcomes = sorted(market.outcomes, key=lambda x: x.odds)

            organized_futures[sport_title].append(
                {
                    "label": game.display_sport_title,
                    "end_date": game.commence_time,
                    "outcomes": sorted_outcomes,
                }
            )

    return render_template("betfake/futures.html", organized_futures=organized_futures)


@betfake_bp.route("/history")
@login_required
def history():
    """View full bet history."""
    # Query all bets for user, joined with necessary info
    bets = (
        BetfakeBet.query.filter_by(user_id=current_user.id)
        .order_by(BetfakeBet.placed_at.desc())
        .all()
    )
    accounts = BetfakeAccount.query.filter_by(user_id=current_user.id).all()

    # Summary stats
    stats = {
        "total_wagered": sum(
            b.wager_amount for b in bets if b.status.value != "Pending"
        ),
        "total_payout": sum(b.potential_payout for b in bets if b.status.value == "Won")
        + sum(b.wager_amount for b in bets if b.status.value == "Push"),
        "wins": len([b for b in bets if b.status.value == "Won"]),
        "losses": len([b for b in bets if b.status.value == "Lost"]),
        "pushes": len([b for b in bets if b.status.value == "Push"]),
        "pending": len([b for b in bets if b.status.value == "Pending"]),
    }

    return render_template(
        "betfake/history.html", bets=bets, stats=stats, accounts=accounts
    )


@betfake_bp.route("/transactions/<int:account_id>")
@login_required
def transactions(account_id):
    """View transactions for a specific account."""
    account = BetfakeAccount.query.get_or_404(account_id)
    if account.user_id != current_user.id:
        flash("Unauthorized account.", "error")
        return redirect(url_for("betfake.index"))

    # Calculate account-level stats
    pending_wagers = (
        db.session.query(db.func.sum(BetfakeBet.wager_amount))
        .filter(
            BetfakeBet.account_id == account.id, BetfakeBet.status == BetStatus.Pending
        )
        .scalar()
        or 0
    )
    account_equity = account.balance + pending_wagers

    settled_bets = BetfakeBet.query.filter(
        BetfakeBet.account_id == account.id,
        BetfakeBet.status.in_([BetStatus.Won, BetStatus.Lost, BetStatus.Push]),
    ).all()

    account_pl = 0
    for bet in settled_bets:
        if bet.status == BetStatus.Won:
            account_pl += bet.potential_payout - bet.wager_amount
        elif bet.status == BetStatus.Lost:
            account_pl -= bet.wager_amount

    formatted_account_pl = format_currency(account_pl)
    if account_pl > 0:
        formatted_account_pl = "+" + formatted_account_pl

    # Order by creation to calculate running balance
    transactions = (
        BetfakeTransaction.query.filter_by(account_id=account.id)
        .order_by(BetfakeTransaction.created_at.asc())
        .all()
    )

    running_balance = 0
    for tx in transactions:
        running_balance += tx.amount
        tx.balance_after = running_balance

    # Reverse to show newest first
    transactions.reverse()

    # Get all accounts for switching
    all_accounts = (
        BetfakeAccount.query.filter_by(user_id=current_user.id)
        .order_by(BetfakeAccount.created_at)
        .all()
    )

    return render_template(
        "betfake/transactions.html",
        account=account,
        transactions=transactions,
        account_equity=account_equity,
        account_pl=account_pl,
        formatted_account_pl=formatted_account_pl,
        all_accounts=all_accounts,
    )


@betfake_bp.route("/game/<int:game_id>")
@login_required
def game_detail(game_id):
    """View details for a specific game, including scores and user bets."""
    game = BetfakeGame.query.get_or_404(game_id)

    # Don't show detail page for futures (they don't have teams)
    if not game.home_team or not game.away_team:
        return redirect(url_for("betfake.futures"))

    # Get all bets the user has on this game
    # We join through outcome and market to filter by game_id
    user_bets = (
        BetfakeBet.query.join(BetfakeOutcome)
        .join(BetfakeMarket)
        .filter(BetfakeBet.user_id == current_user.id, BetfakeMarket.game_id == game.id)
        .order_by(BetfakeBet.placed_at.desc())
        .all()
    )

    # Calculate game P/L
    game_pl = 0
    for bet in user_bets:
        if bet.status == BetStatus.Won:
            game_pl += bet.potential_payout - bet.wager_amount
        elif bet.status == BetStatus.Lost:
            game_pl -= bet.wager_amount

    formatted_game_pl = format_currency(game_pl)
    if game_pl > 0:
        formatted_game_pl = "+" + formatted_game_pl

    # Get available markets if the game hasn't started
    now = datetime.utcnow()
    display_markets = {}
    if game.commence_time > now:
        market_types = [MarketType.h2h, MarketType.spreads, MarketType.totals]
        for mt in market_types:
            # 1. Try DraftKings (Primary)
            market = BetfakeMarket.query.filter_by(
                game_id=game.id, type=mt, bookmaker_key="draftkings", is_active=True
            ).first()

            # 2. Fallback to FanDuel
            if not market:
                market = BetfakeMarket.query.filter_by(
                    game_id=game.id, type=mt, bookmaker_key="fanduel", is_active=True
                ).first()

            if market:
                display_markets[mt.value] = market

    # Get the latest "Closing" or "Last Known" lines for historical reference
    historical_markets = {}
    for mt in [MarketType.h2h, MarketType.spreads, MarketType.totals]:
        m = (
            BetfakeMarket.query.filter_by(game_id=game.id, type=mt)
            .order_by(BetfakeMarket.created_at.desc())
            .first()
        )
        if m:
            historical_markets[mt.value] = m

    # Compute outcome results for completed games
    outcome_results = {}
    if game.status == GameStatus.Completed:
        from app.projects.betfake.services.bet_grader import grade_outcome

        for mt_value, market in historical_markets.items():
            for outcome in market.outcomes:
                outcome_results[outcome.id] = grade_outcome(outcome, game)

    return render_template(
        "betfake/game.html",
        game=game,
        user_bets=user_bets,
        game_pl=game_pl,
        formatted_game_pl=formatted_game_pl,
        display_markets=display_markets,
        historical_markets=historical_markets,
        outcome_results=outcome_results,
        now=now,
    )


@betfake_bp.route("/admin/sync")
@login_required
@admin_required
def admin_sync():
    """Admin page to manually trigger Odds API sync and manage sports."""
    from app.projects.betfake.models import BetfakeSport

    # Get all sports from DB
    all_sports = BetfakeSport.query.order_by(BetfakeSport.sport_title).all()

    # Group into active vs available for the registry table
    reg_active = [
        s for s in all_sports if s.sync_scores or s.sync_odds or s.show_in_nav
    ]
    reg_available = [
        s for s in all_sports if not (s.sync_scores or s.sync_odds or s.show_in_nav)
    ]

    return render_template(
        "betfake/admin_sync.html", reg_active=reg_active, reg_available=reg_available
    )


@betfake_bp.route("/admin/sports/refresh", methods=["POST"])
@login_required
@admin_required
def admin_refresh_sports():
    """Fetch all sports from the Odds API and update the database registry."""
    from app.projects.betfake.services.odds_api import OddsAPIService
    from app.projects.betfake.models import BetfakeSport
    from app.models import LogEntry

    api = OddsAPIService()
    sports_data = api.fetch_sports_list()

    if not sports_data:
        flash("Failed to fetch sports from API.", "error")
        return redirect(url_for("betfake.admin_sync"))

    new_count = 0
    updated_count = 0

    for s in sports_data:
        sport = BetfakeSport.query.filter_by(sport_key=s["key"]).first()
        if not sport:
            sport = BetfakeSport(
                sport_key=s["key"],
                sport_title=s["title"],
                sport_group=s.get("group"),
                has_spreads=True,  # Default to True
                sync_scores=False,
                sync_odds=False,
                show_in_nav=False,
                is_outright=s.get("has_outrights", False),
            )
            db.session.add(sport)
            new_count += 1
        else:
            changed = False
            if sport.sport_title != s["title"]:
                sport.sport_title = s["title"]
                changed = True
            if sport.sport_group != s.get("group"):
                sport.sport_group = s.get("group")
                changed = True
            if sport.is_outright != s.get("has_outrights", False):
                sport.is_outright = s.get("has_outrights", False)
                changed = True

            if changed:
                updated_count += 1

    try:
        db.session.commit()
        msg = f"Sports registry updated. Added {new_count} new, updated {updated_count} names."
        flash(msg, "success")
        db.session.add(LogEntry(project="betfake", category="Admin", description=msg))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating sports registry: {str(e)}", "error")

    return redirect(url_for("betfake.admin_sync"))


@betfake_bp.route("/admin/sports/update", methods=["POST"])
@login_required
@admin_required
def admin_update_sport_config():
    """Update settings (sync_scores, sync_odds, show_in_nav, has_spreads, is_outright) for a sport."""
    from app.projects.betfake.models import BetfakeSport

    sport_id = request.form.get("sport_id")
    sport = BetfakeSport.query.get_or_404(sport_id)

    # Only update fields that were actually sent in the form
    # This prevents the "Enable All" button from overwriting is_outright/has_spreads
    if "sync_scores_sent" in request.form or "sync_scores" in request.form:
        sport.sync_scores = "sync_scores" in request.form
    if "sync_odds_sent" in request.form or "sync_odds" in request.form:
        sport.sync_odds = "sync_odds" in request.form
    if "show_in_nav_sent" in request.form or "show_in_nav" in request.form:
        sport.show_in_nav = "show_in_nav" in request.form
    if "has_spreads_sent" in request.form or "has_spreads" in request.form:
        sport.has_spreads = "has_spreads" in request.form
    # is_outright is never updated from the form; we rely on the API (Refresh from API) for that.
    if "preferred_label_sent" in request.form:
        new_label = request.form.get("preferred_label", "").strip()
        sport.preferred_label = new_label if new_label else None

    # Fallback for the "Enable All" button which sends explicit 'on' values
    if request.form.get("all_enabled") == "true":
        sport.sync_scores = True
        sport.sync_odds = True
        sport.show_in_nav = True
        # Note: We specifically DON'T touch is_outright or has_spreads here

    try:
        db.session.commit()
        from app.models import LogEntry

        log_desc = f"Admin updated {sport.sport_title} config: Nav={sport.show_in_nav}, Odds={sport.sync_odds}, Scores={sport.sync_scores}, Spreads={sport.has_spreads}"
        db.session.add(
            LogEntry(project="betfake", category="Admin", description=log_desc)
        )
        db.session.commit()
        flash(f"Updated configuration for {sport.sport_title}.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating {sport.sport_title}: {str(e)}", "error")

    return redirect(url_for("betfake.admin_sync"))


@betfake_bp.route("/admin/sports/add-manual", methods=["POST"])
@login_required
@admin_required
def admin_add_sport_manual():
    """Manually add a sport key (useful for futures or niche markets)."""
    from app.projects.betfake.models import BetfakeSport
    from app.projects.betfake.services.odds_api import OddsAPIService

    key = request.form.get("sport_key", "").strip()
    title = request.form.get("sport_title", "").strip()
    group = request.form.get("sport_group", "").strip()

    if not key or not title:
        flash("Both key and title are required.", "error")
        return redirect(url_for("betfake.admin_sync"))

    existing = BetfakeSport.query.filter_by(sport_key=key).first()
    if existing:
        flash(f"Sport with key {key} already exists.", "warning")
        return redirect(url_for("betfake.admin_sync"))

    # Get is_outright from API when possible (we always trust the API for type)
    is_outright = False
    api = OddsAPIService()
    sports_data = api.fetch_sports_list()
    if sports_data:
        for s in sports_data:
            if s.get("key") == key:
                is_outright = s.get("has_outrights", False)
                break

    new_sport = BetfakeSport(
        sport_key=key,
        sport_title=title,
        sport_group=group if group else None,
        sync_scores=False,
        sync_odds=False,
        show_in_nav=False,
        is_outright=is_outright,
    )
    db.session.add(new_sport)

    try:
        db.session.commit()
        from app.models import LogEntry

        msg = f"Admin manually added sport: {title} ({key})"
        db.session.add(LogEntry(project="betfake", category="Admin", description=msg))
        db.session.commit()
        flash(f"Manually added {title}.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error adding sport: {str(e)}", "error")

    return redirect(url_for("betfake.admin_sync"))


@betfake_bp.route("/admin/sync/trigger", methods=["POST"])
@login_required
@admin_required
def admin_sync_trigger():
    """Route to trigger the sync process with granular control."""
    from app.projects.betfake.services.bet_grader import BetGraderService
    import time

    sport = request.form.get("sport")
    sync_type = request.form.get("sync_type", "full")  # 'scores', 'odds', or 'full'
    importer = DataImportService()
    grader = BetGraderService()

    # NEW: Fetch dynamic sports from DB based on toggles
    from app.projects.betfake.models import BetfakeSport

    if sport:
        # If a specific sport was passed (rare in new UI but kept for compatibility)
        sports_to_sync_objs = BetfakeSport.query.filter_by(sport_key=sport).all()
    else:
        # Get all sports where the relevant sync toggle is ON
        if sync_type == "scores":
            sports_to_sync_objs = BetfakeSport.query.filter_by(sync_scores=True).all()
        elif sync_type == "odds":
            sports_to_sync_objs = BetfakeSport.query.filter_by(sync_odds=True).all()
        else:  # full
            sports_to_sync_objs = BetfakeSport.query.filter(
                (BetfakeSport.sync_scores == True) | (BetfakeSport.sync_odds == True)
            ).all()

    if not sports_to_sync_objs:
        flash(
            "No sports are enabled for sync. Please enable them in the registry below.",
            "warning",
        )
        return redirect(url_for("betfake.admin_sync"))

    try:
        results = []

        # 1. Sync Scores
        if sync_type in ["scores", "full"]:
            for s_obj in sports_to_sync_objs:
                if not s_obj.sync_scores and sync_type != "full":
                    continue

                s_key = s_obj.sport_key
                count = importer.import_scores_for_sport(s_key)
                quota = importer.api.last_remaining_quota
                log_desc = f"UI Sync Scores: {s_key} updated {count} games."
                if quota:
                    log_desc += f" API Quota remaining: {quota}"
                db.session.add(
                    LogEntry(
                        project="betfake", category="Sync Step", description=log_desc
                    )
                )
                results.append(f"{s_obj.display_title} scores ({count})")

            # Settle bets
            settled_count = grader.settle_pending_bets()
            db.session.add(
                LogEntry(
                    project="betfake",
                    category="Settlement",
                    description=f"UI Settlement: Settled {settled_count} bets.",
                )
            )
            results.append(f"Settled {settled_count} bets")

        # 2. Sync Odds
        if sync_type in ["odds", "full"]:
            for s_obj in sports_to_sync_objs:
                if not s_obj.sync_odds and sync_type != "full":
                    continue

                s_key = s_obj.sport_key
                game_count = importer.import_games_for_sport(s_key)

                # Use the has_spreads flag from DB
                markets = "h2h,spreads,totals" if s_obj.has_spreads else "h2h"

                # Check if it's a futures sport (outright)
                if s_obj.is_outright:
                    market_count = importer.import_futures(s_key)
                else:
                    market_count = importer.import_odds_for_sport(
                        s_key, markets_str=markets
                    )

                quota = importer.api.last_remaining_quota

                log_desc = f"UI Sync Odds: {s_key} imported {game_count} games, {market_count} markets."
                if quota:
                    log_desc += f" API Quota remaining: {quota}"
                db.session.add(
                    LogEntry(
                        project="betfake", category="Sync Step", description=log_desc
                    )
                )
                results.append(
                    f"{s_obj.display_title} odds ({game_count} games, {market_count} markets)"
                )

                time.sleep(0.5)  # Small buffer between sports

        db.session.commit()
        flash(f"Sync complete: {', '.join(results)}", "success")

    except Exception as e:
        db.session.rollback()
        logging.error(f"Sync error: {str(e)}")
        flash(f"Error during sync: {str(e)}", "error")

    return redirect(url_for("betfake.admin_sync"))

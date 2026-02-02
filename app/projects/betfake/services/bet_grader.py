import logging
from datetime import datetime
from app import db
from app.projects.betfake.models import (
    BetfakeBet,
    BetfakeGame,
    BetfakeAccount,
    BetfakeTransaction,
    BetStatus,
    TransactionType,
    MarketType,
    GameStatus,
)

logger = logging.getLogger(__name__)


def grade_outcome(outcome, game):
    """
    Grade an outcome based on the game result.
    Returns 'won', 'lost', 'push', or None if game not completed.
    This is used to show winning/losing lines on the game detail page.
    """
    if game.status != GameStatus.Completed:
        return None
    if game.home_score is None or game.away_score is None:
        return None

    market_type = outcome.market.type

    if market_type == MarketType.h2h:
        # Determine the winner
        if game.home_score > game.away_score:
            winner = game.home_team
        elif game.away_score > game.home_score:
            winner = game.away_team
        else:
            winner = "Draw"

        if outcome.outcome_name == winner:
            return "won"
        else:
            return "lost"

    elif market_type == MarketType.spreads:
        # Spread: team score + spread vs opponent score
        is_home = outcome.outcome_name == game.home_team

        if is_home:
            adjusted = game.home_score + outcome.point_value
            opponent = game.away_score
        else:
            adjusted = game.away_score + outcome.point_value
            opponent = game.home_score

        if adjusted > opponent:
            return "won"
        elif adjusted < opponent:
            return "lost"
        else:
            return "push"

    elif market_type == MarketType.totals:
        # Totals: compare combined score to line
        total = game.home_score + game.away_score
        is_over = "Over" in outcome.outcome_name

        if total > outcome.point_value:
            return "won" if is_over else "lost"
        elif total < outcome.point_value:
            return "lost" if is_over else "won"
        else:
            return "push"

    return None


class BetGraderService:
    def grade_h2h_bet(self, bet, game):
        """Grade a Moneyline (h2h) bet."""
        # 2-outcome sports: winner is home or away
        # 3-outcome sports (soccer): winner is home, away, or draw

        if game.home_score is None or game.away_score is None:
            return None  # Cannot grade yet

        winner_name = None
        if game.home_score > game.away_score:
            winner_name = game.home_team
        elif game.away_score > game.home_score:
            winner_name = game.away_team
        else:
            winner_name = "Draw"

        if bet.outcome_name_at_time == winner_name:
            return BetStatus.Won
        else:
            return BetStatus.Lost

    def grade_spread_bet(self, bet, game):
        """Grade a Point Spread bet."""
        if game.home_score is None or game.away_score is None:
            return None

        # The line is usually for the outcome chosen
        # Example: Bet on Lakers -7.5. outcome_name="Lakers", line=-7.5
        # If Lakers win 110 - 100, diff = 10. 10 > 7.5, so Lakers cover.

        # We need to know if the outcome name is the home or away team to apply the logic
        is_home_bet = bet.outcome_name_at_time == game.home_team

        # Adjusted Score = Team Score + Spread
        # Example: Lakers (Home) -7.5. Adjusted = 110 + (-7.5) = 102.5. 102.5 > 100 (Away score) -> Won

        if is_home_bet:
            adjusted_score = game.home_score + bet.line_at_time
            opponent_score = game.away_score
        else:
            adjusted_score = game.away_score + bet.line_at_time
            opponent_score = game.home_score

        if adjusted_score > opponent_score:
            return BetStatus.Won
        elif adjusted_score < opponent_score:
            return BetStatus.Lost
        else:
            return BetStatus.Push

    def grade_total_bet(self, bet, game):
        """Grade an Over/Under (Total) bet."""
        if game.home_score is None or game.away_score is None:
            return None

        total_score = game.home_score + game.away_score
        is_over = "Over" in bet.outcome_name_at_time

        if total_score > bet.line_at_time:
            return BetStatus.Won if is_over else BetStatus.Lost
        elif total_score < bet.line_at_time:
            return BetStatus.Lost if is_over else BetStatus.Won
        else:
            return BetStatus.Push

    def grade_bet(self, bet):
        """Main grading logic based on market type."""
        game = bet.outcome.market.game
        market_type = bet.outcome.market.type

        if market_type == MarketType.h2h:
            return self.grade_h2h_bet(bet, game)
        elif market_type == MarketType.spreads:
            return self.grade_spread_bet(bet, game)
        elif market_type == MarketType.totals:
            return self.grade_total_bet(bet, game)
        # Futures (outrights) are graded manually or via a different check in Phase 5
        return None

    def settle_pending_bets(self, game_id=None):
        """Find and settle all pending bets for completed games."""
        query = BetfakeBet.query.filter_by(status=BetStatus.Pending)

        if game_id:
            # Settle only for a specific game
            # Joining through outcome -> market -> game
            from app.projects.betfake.models import BetfakeOutcome, BetfakeMarket

            query = (
                query.join(BetfakeOutcome)
                .join(BetfakeMarket)
                .filter(BetfakeMarket.game_id == game_id)
            )

        pending_bets = query.all()
        settled_count = 0

        for bet in pending_bets:
            game = bet.outcome.market.game
            if game.status != GameStatus.Completed:
                continue

            new_status = self.grade_bet(bet)
            if not new_status:
                continue

            # Process settlement transaction
            try:
                bet.status = new_status
                bet.settled_at = datetime.utcnow()

                if new_status == BetStatus.Won:
                    # Payout potential_payout
                    bet.account.balance += bet.potential_payout
                    transaction = BetfakeTransaction(
                        user_id=bet.user_id,
                        account_id=bet.account_id,
                        bet_id=bet.id,
                        amount=bet.potential_payout,
                        type=TransactionType.Payout,
                    )
                    db.session.add(transaction)
                elif new_status == BetStatus.Push:
                    # Refund wager_amount
                    bet.account.balance += bet.wager_amount
                    transaction = BetfakeTransaction(
                        user_id=bet.user_id,
                        account_id=bet.account_id,
                        bet_id=bet.id,
                        amount=bet.wager_amount,
                        type=TransactionType.Payout,
                    )
                    db.session.add(transaction)

                # Log the settlement to Admin logs
                from app.models import LogEntry

                matchup = (
                    f"{game.away_team} @ {game.home_team}"
                    if game.home_team
                    else game.display_sport_title
                )
                log_desc = f"Settled bet {bet.id}: {bet.outcome_name_at_time} in {matchup} as {new_status.value}."
                if new_status == BetStatus.Won:
                    log_desc += f" Payout: ${bet.potential_payout:,.2f}"
                elif new_status == BetStatus.Push:
                    log_desc += f" Refund: ${bet.wager_amount:,.2f}"

                log_entry = LogEntry(
                    project="betfake",
                    category="Settlement",
                    actor_id=bet.user_id,
                    description=log_desc,
                )
                db.session.add(log_entry)

                db.session.commit()
                settled_count += 1
                logger.info(f"Settled bet {bet.id} as {new_status.value}")
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error settling bet {bet.id}: {str(e)}")

        return settled_count

import logging
from datetime import datetime, timezone
import dateutil.parser
from app import db
from app.projects.betfake.models import (
    BetfakeGame,
    BetfakeMarket,
    BetfakeOutcome,
    GameStatus,
    MarketType,
)
from app.projects.betfake.services.odds_api import OddsAPIService

logger = logging.getLogger(__name__)


class DataImportService:
    def __init__(self):
        self.api = OddsAPIService()

    def _parse_iso_datetime(self, dt_str):
        """Parse ISO 8601 datetime string from API."""
        if not dt_str:
            return None
        return dateutil.parser.isoparse(dt_str).replace(tzinfo=None)

    def import_games_for_sport(self, sport_key):
        """Fetch and import games for a sport."""
        events = self.api.fetch_events(sport_key)
        if not events:
            return 0

        count = 0
        for event in events:
            game = BetfakeGame.query.filter_by(external_id=event["id"]).first()
            if not game:
                game = BetfakeGame(external_id=event["id"])
                db.session.add(game)

            game.sport_key = event["sport_key"]
            game.sport_title = event["sport_title"]
            game.home_team = event["home_team"]
            game.away_team = event["away_team"]
            game.commence_time = self._parse_iso_datetime(event["commence_time"])

            # Don't overwrite scores if they already exist
            if game.status != GameStatus.Completed:
                game.status = GameStatus.Scheduled

            count += 1

        db.session.commit()
        logger.info(f"Imported/Updated {count} games for {sport_key}")
        return count

    def import_odds_for_sport(self, sport_key, markets_str="h2h,spreads,totals"):
        """Fetch and import odds for a sport."""
        odds_data = self.api.fetch_odds(sport_key, markets=markets_str)
        if not odds_data:
            return 0

        market_count = 0
        outcome_count = 0
        skipped_live = 0
        now = datetime.utcnow()

        for event in odds_data:
            # Skip games that have already started - don't overwrite pre-game odds with live odds
            commence_time = self._parse_iso_datetime(event.get("commence_time"))
            if commence_time and commence_time < now:
                skipped_live += 1
                continue
            # 1. Ensure game exists
            game = BetfakeGame.query.filter_by(external_id=event["id"]).first()
            if not game:
                game = BetfakeGame(
                    external_id=event["id"],
                    sport_key=event["sport_key"],
                    sport_title=event["sport_title"],
                    home_team=event["home_team"],
                    away_team=event["away_team"],
                    commence_time=self._parse_iso_datetime(event["commence_time"]),
                )
                db.session.add(game)
                db.session.flush()  # Get game.id

            # 2. Process Bookmakers
            for bookmaker in event["bookmakers"]:
                bookmaker_key = bookmaker["key"]

                # 3. Process Markets
                for market in bookmaker["markets"]:
                    market_type_key = market["key"]
                    try:
                        market_type = MarketType(market_type_key)
                    except ValueError:
                        logger.warning(f"Unknown market type: {market_type_key}")
                        continue

                    # Check if active market exists for this game/type/bookmaker
                    active_market = BetfakeMarket.query.filter_by(
                        game_id=game.id,
                        type=market_type,
                        bookmaker_key=bookmaker_key,
                        is_active=True,
                    ).first()

                    # Compare outcomes to see if odds changed
                    should_create_new = False
                    if not active_market:
                        should_create_new = True
                    else:
                        # Compare outcomes
                        existing_outcomes = {
                            o.outcome_name: (o.odds, o.point_value)
                            for o in active_market.outcomes
                        }
                        new_outcomes = {
                            o["name"]: (o["price"], o.get("point"))
                            for o in market["outcomes"]
                        }

                        if existing_outcomes != new_outcomes:
                            should_create_new = True
                            active_market.is_active = False
                            active_market.marked_inactive_at = datetime.utcnow()

                    if should_create_new:
                        new_market = BetfakeMarket(
                            game_id=game.id,
                            type=market_type,
                            bookmaker_key=bookmaker_key,
                            is_active=True,
                            last_update=self._parse_iso_datetime(market["last_update"]),
                        )
                        db.session.add(new_market)
                        db.session.flush()  # Get new_market.id

                        for outcome_data in market["outcomes"]:
                            outcome = BetfakeOutcome(
                                market_id=new_market.id,
                                outcome_name=outcome_data["name"],
                                odds=outcome_data["price"],
                                point_value=outcome_data.get("point"),
                                is_active=True,
                            )
                            db.session.add(outcome)
                            outcome_count += 1

                        market_count += 1

        db.session.commit()
        logger.info(
            f"Imported {market_count} markets and {outcome_count} outcomes for {sport_key} (skipped {skipped_live} live games)"
        )
        return market_count

    def import_futures(self, sport_key):
        """Fetch and import futures (outrights) for a sport key."""
        # Futures are separate sports in the Odds API
        # e.g. basketball_nba_championship_winner
        odds_data = self.api.fetch_odds(sport_key, markets="outrights")
        if not odds_data:
            return 0

        count = 0
        for event in odds_data:
            # For futures, the "event" is the season outcome
            game = BetfakeGame.query.filter_by(external_id=event["id"]).first()
            if not game:
                game = BetfakeGame(
                    external_id=event["id"],
                    sport_key=event["sport_key"],
                    sport_title=event["sport_title"],
                    home_team=None,
                    away_team=None,
                    commence_time=self._parse_iso_datetime(event["commence_time"]),
                    status=GameStatus.Scheduled,
                )
                db.session.add(game)
                db.session.flush()

            # Process bookmakers
            for bookmaker in event["bookmakers"]:
                bookmaker_key = bookmaker["key"]

                for market in bookmaker["markets"]:
                    if market["key"] != "outrights":
                        continue

                    # Check if active market exists
                    active_market = BetfakeMarket.query.filter_by(
                        game_id=game.id,
                        type=MarketType.outrights,
                        bookmaker_key=bookmaker_key,
                        is_active=True,
                    ).first()

                    should_create_new = False
                    if not active_market:
                        should_create_new = True
                    else:
                        # Simple comparison for outrights: just check count and top 5 odds
                        # to avoid massive DB growth while catching major moves
                        existing_outcomes = {
                            o.outcome_name: o.odds for o in active_market.outcomes
                        }
                        new_outcomes = {
                            o["name"]: o["price"] for o in market["outcomes"]
                        }

                        if (
                            len(existing_outcomes) != len(new_outcomes)
                            or existing_outcomes != new_outcomes
                        ):
                            should_create_new = True
                            active_market.is_active = False
                            active_market.marked_inactive_at = datetime.utcnow()

                    if should_create_new:
                        new_market = BetfakeMarket(
                            game_id=game.id,
                            type=MarketType.outrights,
                            bookmaker_key=bookmaker_key,
                            is_active=True,
                            last_update=self._parse_iso_datetime(market["last_update"]),
                        )
                        db.session.add(new_market)
                        db.session.flush()

                        for outcome_data in market["outcomes"]:
                            outcome = BetfakeOutcome(
                                market_id=new_market.id,
                                outcome_name=outcome_data["name"],
                                odds=outcome_data["price"],
                                is_active=True,
                            )
                            db.session.add(outcome)

                        count += 1

        db.session.commit()
        return count

    def import_scores_for_sport(self, sport_key):
        """Fetch and import scores for a sport."""
        scores_data = self.api.fetch_scores(sport_key)
        if not scores_data:
            return 0

        count = 0
        for event in scores_data:
            if not event.get("completed"):
                continue

            game = BetfakeGame.query.filter_by(external_id=event["id"]).first()
            if game:
                game.status = GameStatus.Completed
                # Find scores
                if event.get("scores"):
                    for score in event["scores"]:
                        if score["name"] == game.home_team:
                            game.home_score = int(score["score"])
                        elif score["name"] == game.away_team:
                            game.away_score = int(score["score"])

                game.last_update = datetime.utcnow()
                count += 1

        db.session.commit()
        return count

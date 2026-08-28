"""NFL Survivor pool routes."""

import os
from collections import OrderedDict
from datetime import datetime, timedelta
from functools import wraps

import pytz
import requests
from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import csrf, db
from app.models import User
from app.projects.nfl_survivor import nfl_survivor_bp
from app.projects.nfl_survivor.forms import AdminSetPickForm, SeasonForm, TeamSelectionForm
from app.projects.nfl_survivor.log import log_nfl_survivor
from app.projects.nfl_survivor.models import (
    NflSurvivorParticipant,
    NflSurvivorPick,
    NflSurvivorSeason,
    NflSurvivorSpread,
    NflSurvivorWeeklyResult,
)
from app.projects.nfl_survivor.utils import (
    UTC,
    build_display_names,
    calculate_game_week,
    get_active_season,
    get_current_pick_week,
    get_odds_fetch_window,
    is_join_open,
    is_pick_correct,
    is_scheduled_spreads_day,
    is_team_kickoff_locked,
    is_week_pickable,
    load_nfl_teams,
    load_nfl_teams_as_dict,
    load_nfl_teams_as_pairs,
    map_team_names_to_ids,
    parse_eastern_datetime,
    teams_available_for_week,
    team_pick_choices,
)

EASTERN = pytz.timezone("US/Eastern")
PROJECT = "nfl_survivor"


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            flash("You do not have permission to access this page.")
            return redirect(url_for("nfl_survivor.index"))
        return view(*args, **kwargs)

    return wrapped


def _season_context(season):
    participant = None
    if season and current_user.is_authenticated:
        participant = NflSurvivorParticipant.query.filter_by(
            season_id=season.id, user_id=current_user.id
        ).first()
    return {
        "season": season,
        "is_participant": participant is not None,
        "join_open": season and is_join_open(season),
    }


def _require_season():
    season = get_active_season()
    if not season:
        flash("No active NFL Survivor season. Check back later.")
        return None
    return season


def _require_participant(season):
    participant = NflSurvivorParticipant.query.filter_by(
        season_id=season.id, user_id=current_user.id
    ).first()
    if not participant:
        flash("Join the pool before making or viewing picks.")
        return None
    return participant


def _participants_for_season(season):
    return (
        NflSurvivorParticipant.query.filter_by(season_id=season.id)
        .join(User)
        .order_by(User.full_name.asc())
        .all()
    )


def _participant_users(season):
    return [entry.user for entry in _participants_for_season(season)]


def _spread_favored_class(spread_value):
    if spread_value <= -8:
        return "ns-spread-favored-3"
    if spread_value <= -5:
        return "ns-spread-favored-2"
    if spread_value <= -0.5:
        return "ns-spread-favored-1"
    return ""


@nfl_survivor_bp.app_template_filter("ns_spread_class")
def ns_spread_class_filter(spread_value):
    return _spread_favored_class(spread_value)


@nfl_survivor_bp.route("/")
@login_required
def index():
    season = get_active_season()
    ctx = _season_context(season)
    return render_template("nfl_survivor/index.html", **ctx)


@nfl_survivor_bp.route("/join", methods=["POST"])
@login_required
def join():
    season = _require_season()
    if not season:
        return redirect(url_for("nfl_survivor.index"))

    if not is_join_open(season):
        flash("Join period is closed for this season.")
        return redirect(url_for("nfl_survivor.index"))

    existing = NflSurvivorParticipant.query.filter_by(
        season_id=season.id, user_id=current_user.id
    ).first()
    if existing:
        flash("You are already in the pool.")
        return redirect(url_for("nfl_survivor.index"))

    db.session.add(
        NflSurvivorParticipant(season_id=season.id, user_id=current_user.id)
    )
    log_nfl_survivor(
        "Join",
        f"{current_user.full_name} joined {season.name}",
    )
    db.session.commit()
    flash("You joined the pool!")
    return redirect(url_for("nfl_survivor.index"))


@nfl_survivor_bp.route("/pick", methods=["GET", "POST"])
@login_required
def pick():
    season = _require_season()
    if not season:
        return redirect(url_for("nfl_survivor.index"))
    if not _require_participant(season):
        return redirect(url_for("nfl_survivor.index"))

    current_week = get_current_pick_week(season)
    if current_week > season.max_weeks:
        flash("Season is over.")
        return redirect(url_for("nfl_survivor.view_picks"))

    try:
        selected_week = int(request.args.get("week", current_week))
    except (TypeError, ValueError):
        selected_week = current_week
    if selected_week < current_week or selected_week > season.max_weeks:
        selected_week = current_week

    wrong_picks = NflSurvivorPick.query.filter_by(
        season_id=season.id, user_id=current_user.id, is_correct=False
    ).count()
    if wrong_picks >= 2:
        flash("You have been eliminated.")
        return redirect(url_for("nfl_survivor.view_picks"))

    previous_picks = NflSurvivorPick.query.filter_by(
        season_id=season.id, user_id=current_user.id
    ).all()
    team_lookup = load_nfl_teams_as_dict()
    picked_team_names = OrderedDict(
        (
            p.week,
            (team_lookup.get(p.team, p.team), p.is_correct),
        )
        for p in sorted(previous_picks, key=lambda x: x.week)
    )

    picked_teams_other_weeks = [
        p.team for p in previous_picks if p.week != selected_week
    ]

    existing_pick_for_week = NflSurvivorPick.query.filter_by(
        season_id=season.id, user_id=current_user.id, week=selected_week
    ).first()
    pick_locked = (
        existing_pick_for_week is not None
        and is_team_kickoff_locked(season, selected_week, existing_pick_for_week.team)
    )

    available_teams = teams_available_for_week(
        season, selected_week, picked_teams_other_weeks
    )

    form = TeamSelectionForm()
    form.team_choice.choices = team_pick_choices(
        season, selected_week, available_teams
    )
    form.week.data = str(selected_week)

    if form.validate_on_submit():
        week_num = int(form.week.data)
        picked_for_week = [
            p.team for p in previous_picks if p.week != week_num
        ]
        allowed_teams = teams_available_for_week(season, week_num, picked_for_week)
        allowed_ids = {t[0] for t in allowed_teams}

        if form.team_choice.data not in allowed_ids:
            flash("That team is not available for this week.")
            return redirect(url_for("nfl_survivor.pick", week=week_num))

        if not is_week_pickable(season, week_num):
            flash("That week's pick deadline has passed.")
            return redirect(url_for("nfl_survivor.pick", week=week_num))

        if is_team_kickoff_locked(season, week_num, form.team_choice.data):
            flash("That team's game has already started.")
            return redirect(url_for("nfl_survivor.pick", week=week_num))

        existing_pick = NflSurvivorPick.query.filter_by(
            season_id=season.id, user_id=current_user.id, week=week_num
        ).first()
        if existing_pick and is_team_kickoff_locked(
            season, week_num, existing_pick.team
        ):
            flash("Your pick for this week is locked — that game has started.")
            return redirect(url_for("nfl_survivor.pick", week=week_num))

        team_lookup_for_log = load_nfl_teams_as_dict()
        team_name = team_lookup_for_log.get(
            form.team_choice.data, form.team_choice.data
        )
        if existing_pick:
            old_team_name = team_lookup_for_log.get(
                existing_pick.team, existing_pick.team
            )
            if existing_pick.team != form.team_choice.data:
                pick_description = (
                    f"{current_user.full_name} changed week {week_num} pick from "
                    f"{old_team_name} to {team_name} ({season.name})"
                )
            else:
                pick_description = (
                    f"{current_user.full_name} kept week {week_num} pick: "
                    f"{team_name} ({season.name})"
                )
            existing_pick.team = form.team_choice.data
        else:
            db.session.add(
                NflSurvivorPick(
                    season_id=season.id,
                    user_id=current_user.id,
                    week=week_num,
                    team=form.team_choice.data,
                )
            )
            pick_description = (
                f"{current_user.full_name} picked {team_name} for week {week_num} "
                f"({season.name})"
            )

        log_nfl_survivor("Pick", pick_description)
        db.session.commit()
        flash("Your pick has been submitted.")
        return redirect(url_for("nfl_survivor.pick", week=week_num))

    week_closed = not is_week_pickable(season, selected_week)

    if not form.is_submitted() and existing_pick_for_week:
        form.team_choice.data = existing_pick_for_week.team

    current_time_utc = datetime.now(UTC)
    time_24_hours_ago = current_time_utc - timedelta(hours=24)
    spreads = (
        NflSurvivorSpread.query.filter_by(season_id=season.id)
        .filter(NflSurvivorSpread.game_time > time_24_hours_ago.replace(tzinfo=None))
        .order_by(NflSurvivorSpread.game_time)
        .all()
    )
    spreads_by_week = {}
    for spread in spreads:
        game_time = spread.game_time
        if game_time.tzinfo is None:
            game_time = UTC.localize(game_time)
        spread.game_time = game_time.astimezone(EASTERN)
        spreads_by_week.setdefault(spread.week, []).append(spread)

    last_updated = (
        db.session.query(db.func.max(NflSurvivorSpread.update_time))
        .filter_by(season_id=season.id, week=current_week)
        .scalar()
    )
    if last_updated is None:
        max_week = (
            db.session.query(db.func.max(NflSurvivorSpread.week))
            .filter_by(season_id=season.id)
            .scalar()
        )
        if max_week:
            last_updated = (
                db.session.query(db.func.max(NflSurvivorSpread.update_time))
                .filter_by(season_id=season.id, week=max_week)
                .scalar()
            )
    last_updated_time = None
    if last_updated:
        if last_updated.tzinfo is None:
            last_updated = UTC.localize(last_updated)
        last_updated_time = last_updated.astimezone(EASTERN)

    ctx = _season_context(season)
    return render_template(
        "nfl_survivor/pick.html",
        form=form,
        all_picks=picked_team_names,
        spreads_by_week=spreads_by_week,
        last_updated_time=last_updated_time,
        current_week=current_week,
        selected_week=selected_week,
        existing_pick_for_week=existing_pick_for_week,
        pick_locked=pick_locked,
        week_closed=week_closed,
        available_teams=available_teams,
        team_lookup=team_lookup,
        **ctx,
    )


@nfl_survivor_bp.route("/view-picks")
@login_required
def view_picks():
    season = _require_season()
    if not season:
        return redirect(url_for("nfl_survivor.index"))
    if not _require_participant(season):
        return redirect(url_for("nfl_survivor.index"))

    current_week = get_current_pick_week(season)
    users = _participant_users(season)
    display_names = build_display_names(users)
    team_lookup = load_nfl_teams_as_dict()

    wrong_picks_count = {}
    correct_picks_count = {}
    for user in users:
        wrong_picks_count[user.id] = NflSurvivorPick.query.filter_by(
            season_id=season.id, user_id=user.id, is_correct=False
        ).count()
        correct_picks_count[user.id] = NflSurvivorPick.query.filter_by(
            season_id=season.id, user_id=user.id, is_correct=True
        ).count()

    sorted_users = sorted(
        users,
        key=lambda user: (
            wrong_picks_count.get(user.id, 0),
            -correct_picks_count.get(user.id, 0),
            (display_names[user.id] or "").lower(),
        ),
    )

    all_picks = {}
    for week in range(1, current_week):
        all_picks[week] = {}
        picks_for_week = NflSurvivorPick.query.filter_by(
            season_id=season.id, week=week
        ).all()
        for pick in picks_for_week:
            if pick.user_id not in display_names:
                continue
            team_name = team_lookup.get(pick.team, pick.team)
            all_picks[week][pick.user_id] = {
                "team": team_name,
                "is_correct": pick.is_correct,
            }

    ctx = _season_context(season)
    return render_template(
        "nfl_survivor/view_picks.html",
        all_picks=all_picks,
        sorted_users=sorted_users,
        display_names=display_names,
        wrong_picks_count=wrong_picks_count,
        **ctx,
    )


@nfl_survivor_bp.route("/admin", methods=["GET", "POST"])
@admin_required
def admin():
    season = _require_season()
    if not season:
        return redirect(url_for("nfl_survivor.index"))

    teams = load_nfl_teams()
    current_week = get_current_pick_week(season) - 1
    if current_week < 1:
        current_week = 1

    if request.method == "POST":
        for team in teams:
            team_id = team["id"]
            result = request.form.get(f"result_{team_id}")
            weekly_result = NflSurvivorWeeklyResult.query.filter_by(
                season_id=season.id, week=current_week, team=team_id
            ).first()
            if weekly_result:
                weekly_result.result = result
            else:
                db.session.add(
                    NflSurvivorWeeklyResult(
                        season_id=season.id,
                        week=current_week,
                        team=team_id,
                        result=result,
                    )
                )

        all_picks = NflSurvivorPick.query.filter_by(
            season_id=season.id, week=current_week
        ).all()
        for pick in all_picks:
            pick.is_correct = is_pick_correct(season.id, pick.team, current_week)

        log_nfl_survivor(
            "Set Results",
            f"{current_user.full_name} set results for week {current_week} ({season.name})",
        )
        db.session.commit()
        flash("Weekly results updated.")
        return redirect(url_for("nfl_survivor.view_picks"))

    existing_results = {
        result.team: result.result
        for result in NflSurvivorWeeklyResult.query.filter_by(
            season_id=season.id, week=current_week
        ).all()
    }
    ctx = _season_context(season)
    return render_template(
        "nfl_survivor/admin.html",
        teams=teams,
        week=current_week,
        existing_results=existing_results,
        **ctx,
    )


@nfl_survivor_bp.route("/admin/set-pick", methods=["GET", "POST"])
@admin_required
def admin_set_pick():
    season = _require_season()
    if not season:
        return redirect(url_for("nfl_survivor.index"))

    participants = _participants_for_season(season)
    display_names = build_display_names([p.user for p in participants])
    form = AdminSetPickForm()
    form.user_id.choices = [(p.user_id, display_names[p.user_id]) for p in participants]
    form.week.choices = [(str(w), str(w)) for w in range(1, season.max_weeks + 1)]
    form.team.choices = load_nfl_teams_as_pairs()

    if form.validate_on_submit():
        user_id = form.user_id.data
        week_num = int(form.week.data)
        existing_pick = NflSurvivorPick.query.filter_by(
            season_id=season.id, user_id=user_id, week=week_num
        ).first()
        team_lookup = load_nfl_teams_as_dict()
        team_name = team_lookup.get(form.team.data, form.team.data)
        if existing_pick:
            old_team_name = team_lookup.get(existing_pick.team, existing_pick.team)
            if existing_pick.team != form.team.data:
                pick_description = (
                    f"Admin {current_user.full_name} changed pick for "
                    f"{display_names[user_id]} week {week_num} from {old_team_name} "
                    f"to {team_name} ({season.name})"
                )
            else:
                pick_description = (
                    f"Admin {current_user.full_name} set pick for "
                    f"{display_names[user_id]} week {week_num}: {team_name} ({season.name})"
                )
            existing_pick.team = form.team.data
        else:
            db.session.add(
                NflSurvivorPick(
                    season_id=season.id,
                    user_id=user_id,
                    week=week_num,
                    team=form.team.data,
                )
            )
            pick_description = (
                f"Admin {current_user.full_name} set pick for "
                f"{display_names[user_id]} week {week_num}: {team_name} ({season.name})"
            )

        log_nfl_survivor("Pick", pick_description)
        db.session.commit()
        flash("Pick set successfully.")
        return redirect(url_for("nfl_survivor.admin_set_pick"))

    ctx = _season_context(season)
    return render_template("nfl_survivor/admin_set_pick.html", form=form, **ctx)


@nfl_survivor_bp.route("/admin/view-picks")
@admin_required
def admin_view_picks():
    season = _require_season()
    if not season:
        return redirect(url_for("nfl_survivor.index"))

    current_week = get_current_pick_week(season)
    team_lookup = load_nfl_teams_as_dict()
    participants = _participants_for_season(season)
    display_names = build_display_names([p.user for p in participants])

    picks = []
    for participant in participants:
        pick = NflSurvivorPick.query.filter_by(
            season_id=season.id, user_id=participant.user_id, week=current_week
        ).first()
        team_name = (
            team_lookup.get(pick.team, "Not Picked") if pick else "Not Picked"
        )
        picks.append((display_names[participant.user_id], team_name))

    ctx = _season_context(season)
    return render_template(
        "nfl_survivor/admin_view_picks.html",
        picks=picks,
        week=current_week,
        **ctx,
    )


@nfl_survivor_bp.route("/admin/auto-pick", methods=["GET", "POST"])
@admin_required
def admin_auto_pick():
    season = _require_season()
    if not season:
        return redirect(url_for("nfl_survivor.index"))

    if request.method == "POST":
        week_number = int(request.form["week_number"])
        participants = _participants_for_season(season)
        name_to_id = {team["name"]: team["id"] for team in load_nfl_teams()}
        display_names = build_display_names([p.user for p in participants])

        for participant in participants:
            user = participant.user
            if _user_has_two_wrong_picks(season, user.id):
                continue
            if _user_made_pick_for_week(season, user.id, week_number):
                continue
            previously_picked = _get_previously_picked_team_names(
                season, user.id, week_number
            )
            team_to_pick = _find_team_with_most_negative_spread(
                season, previously_picked, week_number
            )
            if not team_to_pick:
                continue
            team_id = name_to_id.get(team_to_pick)
            db.session.add(
                NflSurvivorPick(
                    season_id=season.id,
                    user_id=user.id,
                    week=week_number,
                    team=team_id,
                    is_correct=None,
                )
            )
            log_nfl_survivor(
                "Pick",
                f"Auto-pick: {current_user.full_name} assigned {team_to_pick} to "
                f"{display_names[user.id]} for week {week_number} ({season.name})",
            )

        db.session.commit()
        flash(f"Auto picks set for week {week_number}.")
        return redirect(url_for("admin.view_logs", project=PROJECT))

    ctx = _season_context(season)
    return render_template("nfl_survivor/admin_auto_pick.html", **ctx)


@nfl_survivor_bp.route("/admin/auto-update", methods=["GET", "POST"])
@admin_required
def auto_update():
    season = _require_season()
    if not season:
        return redirect(url_for("nfl_survivor.index"))

    if request.method == "POST":
        week_number = request.form.get("week_number")
        if week_number:
            try:
                week_number = int(week_number)
                results = _fetch_results_for_week(season, week_number)
                _update_weekly_results(season, week_number, results)
                flash(f"Weekly results updated for week {week_number}.")
            except ValueError:
                flash("Invalid week number.")
            except Exception as exc:
                week_label = week_number if week_number else "unknown"
                log_nfl_survivor(
                    "Auto Update",
                    f"{current_user.full_name} auto-update failed for week "
                    f"{week_label} ({season.name}): {exc}",
                )
                db.session.commit()
                flash(f"Error updating results: {exc}")
        return redirect(url_for("nfl_survivor.auto_update"))

    ctx = _season_context(season)
    return render_template("nfl_survivor/auto_update.html", **ctx)


@nfl_survivor_bp.route("/admin/fetch-schedule")
@admin_required
def fetch_schedule():
    season = _require_season()
    if not season:
        return redirect(url_for("nfl_survivor.index"))

    from app.projects.nfl_survivor.schedule import fetch_schedule_for_active_weeks

    try:
        total, weeks = fetch_schedule_for_active_weeks(
            season, actor_id=current_user.id, source="manual"
        )
        flash(f"Schedule updated for weeks {weeks} ({total} team rows).")
    except Exception as exc:
        log_nfl_survivor(
            "Fetch Schedule",
            f"Manual fetch schedule failed ({season.name}): {exc}",
        )
        db.session.commit()
        flash(f"Schedule fetch failed: {exc}")

    return redirect(url_for("nfl_survivor.pick"))


@nfl_survivor_bp.route("/admin/fetch-spreads")
@admin_required
def fetch_spreads():
    season = _require_season()
    if not season:
        return redirect(url_for("nfl_survivor.index"))
    result = _fetch_spreads_data(season, manual=True)
    if isinstance(result, tuple):
        return result
    ctx = _season_context(season)
    return render_template("nfl_survivor/fetch_spreads.html", **result, **ctx)


@nfl_survivor_bp.route("/api/fetch-spreads", methods=["GET"])
@csrf.exempt
def api_fetch_spreads():
    api_key = request.headers.get("X-API-Key")
    expected_key = os.environ.get("NFL_SURVIVOR_CRON_API_KEY")
    if not expected_key or api_key != expected_key:
        return jsonify({"error": "Invalid API key"}), 401

    season = get_active_season()
    if not season:
        return jsonify({"error": "No active season"}), 404

    if not is_scheduled_spreads_day():
        log_nfl_survivor(
            "Fetch Spreads",
            "Cron fetch spreads skipped (not Tuesday or Thursday, US/Eastern)",
            actor_id=None,
        )
        db.session.commit()
        return jsonify(
            {
                "success": True,
                "skipped": True,
                "message": "Spreads fetch only runs on Tuesday and Thursday (US/Eastern).",
            }
        )

    result = _fetch_spreads_data(season, manual=False)
    if isinstance(result, tuple):
        body, status = result
        return jsonify(body), status
    return jsonify(
        {
            "success": True,
            "message": result["message"],
            "remaining_requests": result["remaining_requests"],
            "used_requests": result["used_requests"],
            "last_updated_time": result["last_updated_time"].isoformat(),
        }
    )


@nfl_survivor_bp.route("/admin/all-spreads")
@admin_required
def all_spreads():
    season = _require_season()
    if not season:
        return redirect(url_for("nfl_survivor.index"))

    spreads = (
        NflSurvivorSpread.query.filter_by(season_id=season.id)
        .order_by(NflSurvivorSpread.week, NflSurvivorSpread.game_time)
        .all()
    )
    spreads_by_week = {}
    for spread in spreads:
        game_time = spread.game_time
        if game_time.tzinfo is None:
            game_time = UTC.localize(game_time)
        spread.game_time = game_time.astimezone(EASTERN)
        spreads_by_week.setdefault(spread.week, []).append(spread)

    ctx = _season_context(season)
    return render_template(
        "nfl_survivor/all_spreads.html", spreads_by_week=spreads_by_week, **ctx
    )


@nfl_survivor_bp.route("/admin/view-weekly-results")
@admin_required
def admin_view_weekly_results():
    season = _require_season()
    if not season:
        return redirect(url_for("nfl_survivor.index"))

    team_dict = load_nfl_teams_as_dict()
    weekly_results = NflSurvivorWeeklyResult.query.filter_by(season_id=season.id).all()
    results_by_team = {}
    for result in weekly_results:
        team_name = team_dict.get(result.team, "Unknown Team")
        if team_name not in results_by_team:
            results_by_team[team_name] = {
                week: "" for week in range(1, season.max_weeks)
            }
        results_by_team[team_name][result.week] = result.result

    ctx = _season_context(season)
    return render_template(
        "nfl_survivor/admin_view_weekly_results.html",
        results_by_team=dict(sorted(results_by_team.items())),
        max_weeks=season.max_weeks,
        **ctx,
    )


@nfl_survivor_bp.route("/admin/view-all-picks")
@admin_required
def admin_view_all_picks():
    season = _require_season()
    if not season:
        return redirect(url_for("nfl_survivor.index"))

    participants = _participants_for_season(season)
    display_names = build_display_names([p.user for p in participants])
    team_lookup = load_nfl_teams_as_dict()
    picks = NflSurvivorPick.query.filter_by(season_id=season.id).all()

    picks_by_user = {
        display_names[p.user_id]: {week: "" for week in range(1, season.max_weeks + 1)}
        for p in participants
    }
    for pick in picks:
        if pick.user_id not in display_names:
            continue
        picks_by_user[display_names[pick.user_id]][pick.week] = team_lookup.get(
            pick.team, pick.team
        )

    ctx = _season_context(season)
    return render_template(
        "nfl_survivor/admin_view_all_picks.html",
        picks_by_user=picks_by_user,
        max_weeks=season.max_weeks,
        **ctx,
    )


@nfl_survivor_bp.route("/admin/participants")
@admin_required
def admin_view_participants():
    season = _require_season()
    if not season:
        return redirect(url_for("nfl_survivor.index"))

    current_week = get_current_pick_week(season)
    participants = _participants_for_season(season)
    display_names = build_display_names([p.user for p in participants])
    rows = []
    for participant in participants:
        picks = NflSurvivorPick.query.filter_by(
            season_id=season.id, user_id=participant.user_id
        ).all()
        wrong_picks = sum(1 for pick in picks if pick.is_correct is False)
        has_picked = any(pick.week == current_week for pick in picks)
        needs_to_pick = wrong_picks < 2 and not has_picked
        rows.append(
            {
                "name": display_names[participant.user_id],
                "picks_count": len(picks),
                "wrong_picks": wrong_picks,
                "needs_to_pick": needs_to_pick,
            }
        )

    ctx = _season_context(season)
    return render_template(
        "nfl_survivor/admin_view_participants.html",
        participants=rows,
        current_week=current_week,
        **ctx,
    )


@nfl_survivor_bp.route("/admin/seasons")
@admin_required
def admin_seasons():
    seasons = NflSurvivorSeason.query.order_by(NflSurvivorSeason.year.desc()).all()
    ctx = _season_context(get_active_season())
    return render_template("nfl_survivor/admin_seasons.html", seasons=seasons, **ctx)


@nfl_survivor_bp.route("/admin/seasons/new", methods=["GET", "POST"])
@admin_required
def admin_season_new():
    form = SeasonForm()
    if form.validate_on_submit():
        if form.is_active.data:
            NflSurvivorSeason.query.update({NflSurvivorSeason.is_active: False})

        season = NflSurvivorSeason(
            year=form.year.data,
            name=form.name.data,
            week_2_start=parse_eastern_datetime(form.week_2_start.data),
            espn_season_year=form.espn_season_year.data,
            max_weeks=form.max_weeks.data or 18,
            is_active=form.is_active.data,
        )
        db.session.add(season)
        log_nfl_survivor("Season", f"{current_user.full_name} created season {season.name}")
        db.session.commit()
        flash(f"Season {season.name} created.")
        return redirect(url_for("nfl_survivor.admin_seasons"))

    ctx = _season_context(get_active_season())
    return render_template("nfl_survivor/admin_season_form.html", form=form, **ctx)


def _fetch_spreads_data(season, manual=False):
    api_key = os.environ.get("ODDS_API_KEY")
    if not api_key:
        msg = "ODDS_API_KEY is not configured."
        if not manual:
            log_nfl_survivor("Fetch Spreads", f"Cron fetch spreads failed: {msg}", actor_id=None)
            db.session.commit()
        if manual:
            flash(msg)
            return redirect(url_for("nfl_survivor.index"))
        return {"error": msg}, 500

    current_week = get_current_pick_week(season)
    window_start, window_end = get_odds_fetch_window(season, current_week)
    commence_from = max(datetime.now(UTC), window_start.astimezone(UTC))
    commence_to = window_end.astimezone(UTC)

    odds_response = requests.get(
        "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds",
        params={
            "api_key": api_key,
            "bookmakers": "draftkings,fanduel",
            "markets": "spreads",
            "oddsFormat": "american",
            "dateFormat": "unix",
            "commenceTimeFrom": commence_from.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "commenceTimeTo": commence_to.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        timeout=30,
    )

    if odds_response.status_code != 200:
        msg = (
            f"Failed to get odds: status {odds_response.status_code}, "
            f"body {odds_response.text}"
        )
        if not manual:
            log_nfl_survivor(
                "Fetch Spreads",
                f"Cron fetch spreads failed for week {current_week} ({season.name}): {msg}",
                actor_id=None,
            )
            db.session.commit()
        if manual:
            flash(msg)
            return redirect(url_for("nfl_survivor.index"))
        return {"error": msg}, 500

    for game in odds_response.json():
        odds_id = game["id"]
        game_time_utc = datetime.fromtimestamp(game["commence_time"], UTC)
        home_team = game["home_team"]
        away_team = game["away_team"]

        draftkings_data = None
        fanduel_data = None
        for bookmaker in game["bookmakers"]:
            if bookmaker["key"] == "draftkings":
                draftkings_data = bookmaker
            elif bookmaker["key"] == "fanduel":
                fanduel_data = bookmaker
        spread_data = draftkings_data or fanduel_data
        if not spread_data:
            continue

        existing = NflSurvivorSpread.query.filter_by(
            season_id=season.id, odds_id=odds_id
        ).first()
        update_time = datetime.utcnow()
        week = calculate_game_week(season, game_time_utc)

        if existing:
            existing.update_time = update_time
            existing.game_time = game_time_utc.replace(tzinfo=None)
            existing.home_team = home_team
            existing.road_team = away_team
            existing.week = week
            for outcome in spread_data["markets"][0]["outcomes"]:
                if outcome["name"] == home_team:
                    existing.home_team_spread = outcome["point"]
                elif outcome["name"] == away_team:
                    existing.road_team_spread = outcome["point"]
        else:
            spread = NflSurvivorSpread(
                season_id=season.id,
                odds_id=odds_id,
                update_time=update_time,
                game_time=game_time_utc.replace(tzinfo=None),
                home_team=home_team,
                road_team=away_team,
                week=week,
                home_team_spread=0,
                road_team_spread=0,
            )
            for outcome in spread_data["markets"][0]["outcomes"]:
                if outcome["name"] == home_team:
                    spread.home_team_spread = outcome["point"]
                elif outcome["name"] == away_team:
                    spread.road_team_spread = outcome["point"]
            db.session.add(spread)

    log_nfl_survivor(
        "Fetch Spreads",
        f"{'Manual' if manual else 'Cron'} fetch spreads for week {current_week} ({season.name})",
        actor_id=current_user.id if manual and current_user.is_authenticated else None,
    )
    db.session.commit()

    remaining_requests = odds_response.headers.get("x-requests-remaining")
    used_requests = odds_response.headers.get("x-requests-used")

    time_24_hours_ago = datetime.utcnow() - timedelta(hours=24)
    spreads = (
        NflSurvivorSpread.query.filter_by(season_id=season.id)
        .filter(NflSurvivorSpread.game_time > time_24_hours_ago)
        .order_by(NflSurvivorSpread.game_time)
        .all()
    )
    for spread in spreads:
        game_time = spread.game_time
        if game_time.tzinfo is None:
            game_time = UTC.localize(game_time)
        spread.game_time = game_time.astimezone(EASTERN)

    last_updated = (
        db.session.query(db.func.max(NflSurvivorSpread.update_time))
        .filter_by(season_id=season.id, week=current_week)
        .scalar()
    )
    if last_updated is None:
        max_week = (
            db.session.query(db.func.max(NflSurvivorSpread.week))
            .filter_by(season_id=season.id)
            .scalar()
        )
        if max_week:
            last_updated = (
                db.session.query(db.func.max(NflSurvivorSpread.update_time))
                .filter_by(season_id=season.id, week=max_week)
                .scalar()
            )
    last_updated_time = None
    if last_updated:
        if last_updated.tzinfo is None:
            last_updated = UTC.localize(last_updated)
        last_updated_time = last_updated.astimezone(EASTERN)

    payload = {
        "message": f"Successfully fetched spreads for week {current_week}",
        "spreads": spreads,
        "last_updated_time": last_updated_time,
        "current_week": current_week,
        "remaining_requests": remaining_requests,
        "used_requests": used_requests,
    }
    return payload


def _fetch_results_for_week(season, week):
    url = (
        "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
        f"?dates={season.espn_season_year}&seasontype=2&week={week}"
    )
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    data = response.json()
    teams_on_bye = {
        team["displayName"]: "did not play"
        for team in data.get("week", {}).get("teamsOnBye", [])
    }
    game_results = {}
    for event in data.get("events", []):
        for competition in event.get("competitions", []):
            for competitor in competition.get("competitors", []):
                team_name = competitor["team"]["displayName"]
                result = "win" if competitor.get("winner", True) else "lose"
                game_results[team_name] = result
    return {**teams_on_bye, **game_results}


def _update_weekly_results(season, week, results):
    team_name_to_id = map_team_names_to_ids()
    for team_name, result in results.items():
        team_id = team_name_to_id.get(team_name)
        if not team_id:
            continue
        weekly_result = NflSurvivorWeeklyResult.query.filter_by(
            season_id=season.id, week=week, team=team_id
        ).first()
        if weekly_result:
            weekly_result.result = result
        else:
            db.session.add(
                NflSurvivorWeeklyResult(
                    season_id=season.id,
                    week=week,
                    team=team_id,
                    result=result,
                )
            )

    log_nfl_survivor(
        "Auto Update",
        f"{current_user.full_name} auto-updated results for week {week} ({season.name})",
    )
    db.session.commit()

    all_picks = NflSurvivorPick.query.filter_by(season_id=season.id, week=week).all()
    for pick in all_picks:
        pick.is_correct = is_pick_correct(season.id, pick.team, week)
    db.session.commit()


def _user_has_two_wrong_picks(season, user_id):
    return (
        NflSurvivorPick.query.filter_by(
            season_id=season.id, user_id=user_id, is_correct=False
        ).count()
        >= 2
    )


def _user_made_pick_for_week(season, user_id, week):
    return (
        NflSurvivorPick.query.filter_by(
            season_id=season.id, user_id=user_id, week=week
        ).first()
        is not None
    )


def _get_previously_picked_team_names(season, user_id, up_to_week):
    picks = NflSurvivorPick.query.filter(
        NflSurvivorPick.season_id == season.id,
        NflSurvivorPick.user_id == user_id,
        NflSurvivorPick.week < up_to_week,
    ).all()
    team_lookup = load_nfl_teams_as_dict()
    return [team_lookup.get(pick.team, pick.team) for pick in picks]


def _find_team_with_most_negative_spread(season, previously_picked_teams, week_number):
    spreads = NflSurvivorSpread.query.filter_by(
        season_id=season.id, week=week_number
    ).all()
    most_negative_spread = None
    team_to_pick = None
    for spread in spreads:
        if spread.home_team not in previously_picked_teams and (
            most_negative_spread is None
            or spread.home_team_spread < most_negative_spread
        ):
            most_negative_spread = spread.home_team_spread
            team_to_pick = spread.home_team
        if spread.road_team not in previously_picked_teams and (
            most_negative_spread is None
            or spread.road_team_spread < most_negative_spread
        ):
            most_negative_spread = spread.road_team_spread
            team_to_pick = spread.road_team
    return team_to_pick

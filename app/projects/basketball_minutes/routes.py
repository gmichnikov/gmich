"""
Basketball Minutes views and JSON API endpoints.
"""

from datetime import date, datetime
from flask import (
    Blueprint,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import func

from app import db
from app.projects.basketball_minutes.logic import (
    compute_scoring,
    compute_stints_and_minutes,
    current_period_info,
    format_duration,
    format_remaining_time,
    game_phase,
    get_game_roster,
    last_event_time,
    ordered_events,
    parse_time_input,
    replay_lineup,
)
from app.projects.basketball_minutes.models import (
    BkmEvent,
    BkmGame,
    BkmGameRosterEntry,
    BkmPlayer,
    BkmTeam,
    DEFAULT_PERIOD_COUNT,
    DEFAULT_PERIOD_MINUTES,
)
from app.utils.logging import log_project_visit

basketball_minutes_bp = Blueprint(
    "basketball_minutes",
    __name__,
    url_prefix="/basketball-minutes",
    template_folder="templates",
    static_folder="static",
    static_url_path="/basketball-minutes/static",
)


def _get_team_or_404(team_id):
    team = BkmTeam.query.get(team_id)
    if team is None or team.user_id != current_user.id:
        abort(404)
    return team


def _get_player_or_404(team_id, player_id):
    team = _get_team_or_404(team_id)
    player = BkmPlayer.query.filter_by(id=player_id, team_id=team.id).first()
    if player is None:
        abort(404)
    return team, player


def _get_game_or_404(team_id, game_id):
    team = _get_team_or_404(team_id)
    game = BkmGame.query.filter_by(id=game_id, team_id=team.id).first()
    if game is None:
        abort(404)
    return team, game


@basketball_minutes_bp.route("/")
@login_required
def index():
    log_project_visit("basketball_minutes")
    teams = (
        BkmTeam.query.filter_by(user_id=current_user.id)
        .order_by(BkmTeam.updated_at.desc())
        .all()
    )
    return render_template("basketball_minutes/index.html", teams=teams)


@basketball_minutes_bp.route("/teams/new", methods=["GET", "POST"])
@login_required
def team_new():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        season_label = request.form.get("season_label", "").strip() or None
        
        try:
            period_count = int(request.form.get("period_count", DEFAULT_PERIOD_COUNT))
            if period_count not in (2, 4):
                period_count = DEFAULT_PERIOD_COUNT
        except (ValueError, TypeError):
            period_count = DEFAULT_PERIOD_COUNT

        try:
            period_minutes = int(request.form.get("period_minutes", DEFAULT_PERIOD_MINUTES))
            if period_minutes < 1:
                period_minutes = DEFAULT_PERIOD_MINUTES
        except (ValueError, TypeError):
            period_minutes = DEFAULT_PERIOD_MINUTES

        if not name:
            flash("Team name is required.", "danger")
            return render_template("basketball_minutes/team_new.html")

        team = BkmTeam(
            user_id=current_user.id,
            name=name,
            season_label=season_label,
            default_period_count=period_count,
            default_period_minutes=period_minutes,
        )
        db.session.add(team)
        db.session.commit()
        flash(f'Created team "{team.name}".', "success")
        return redirect(url_for("basketball_minutes.team_detail", team_id=team.id))

    return render_template("basketball_minutes/team_new.html")


@basketball_minutes_bp.route("/teams/<int:team_id>")
@login_required
def team_detail(team_id):
    team = _get_team_or_404(team_id)
    players = team.players.order_by(BkmPlayer.sort_order, BkmPlayer.id).all()
    games = team.games.order_by(BkmGame.game_date.desc(), BkmGame.id.desc()).all()
    
    # Calculate season stats for each player
    # Total minutes, total games with minutes, total points
    player_totals = {
        p.id: {"seconds": 0, "points": 0, "games": 0, "ft_made": 0, "ft_att": 0}
        for p in players
    }
    
    for g in games:
        _, p_secs, _ = compute_stints_and_minutes(g)
        _, p_stats = compute_scoring(g)
        for pid, secs in p_secs.items():
            if pid in player_totals:
                player_totals[pid]["seconds"] += secs
                if secs > 0:
                    player_totals[pid]["games"] += 1
        for pid, stats in p_stats.items():
            if pid in player_totals:
                player_totals[pid]["points"] += stats["points"]
                player_totals[pid]["ft_made"] += stats["ft_made"]
                player_totals[pid]["ft_att"] += stats["ft_att"]

    for p in players:
        p.season_seconds = player_totals[p.id]["seconds"]
        p.season_duration = format_duration(p.season_seconds)
        p.season_points = player_totals[p.id]["points"]
        p.season_games = player_totals[p.id]["games"]
        att = player_totals[p.id]["ft_att"]
        made = player_totals[p.id]["ft_made"]
        p.season_ft_str = f"{made}/{att}" if att > 0 else "-"

    return render_template(
        "basketball_minutes/team_detail.html",
        team=team,
        players=players,
        games=games,
    )


@basketball_minutes_bp.route("/teams/<int:team_id>/edit", methods=["GET", "POST"])
@login_required
def team_edit(team_id):
    team = _get_team_or_404(team_id)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        season_label = request.form.get("season_label", "").strip() or None
        try:
            period_count = int(request.form.get("period_count", 4))
            period_minutes = int(request.form.get("period_minutes", 8))
        except (ValueError, TypeError):
            period_count = 4
            period_minutes = 8

        if not name:
            flash("Team name is required.", "danger")
            return render_template("basketball_minutes/team_edit.html", team=team)

        team.name = name
        team.season_label = season_label
        team.default_period_count = period_count
        team.default_period_minutes = period_minutes
        db.session.commit()
        flash("Team updated.", "success")
        return redirect(url_for("basketball_minutes.team_detail", team_id=team.id))

    return render_template("basketball_minutes/team_edit.html", team=team)


@basketball_minutes_bp.route("/teams/<int:team_id>/delete", methods=["POST"])
@login_required
def team_delete(team_id):
    team = _get_team_or_404(team_id)
    name = team.name
    db.session.delete(team)
    db.session.commit()
    flash(f'Team "{name}" deleted.', "success")
    return redirect(url_for("basketball_minutes.index"))


# -------------------------------------------------------------------------
# Player Roster Endpoints
# -------------------------------------------------------------------------

@basketball_minutes_bp.route("/teams/<int:team_id>/players/new", methods=["POST"])
@login_required
def player_create(team_id):
    team = _get_team_or_404(team_id)
    first_name = request.form.get("first_name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    jersey_number = request.form.get("jersey_number", "").strip() or None

    if not first_name or not last_name:
        flash("First and last name are required.", "danger")
        return redirect(url_for("basketball_minutes.team_detail", team_id=team.id))

    max_order = (
        db.session.query(func.max(BkmPlayer.sort_order))
        .filter_by(team_id=team.id)
        .scalar()
        or 0
    )
    player = BkmPlayer(
        team_id=team.id,
        first_name=first_name,
        last_name=last_name,
        jersey_number=jersey_number,
        sort_order=max_order + 1,
    )
    db.session.add(player)
    db.session.commit()
    flash(f"Added player {player.full_name}.", "success")
    return redirect(url_for("basketball_minutes.team_detail", team_id=team.id))


@basketball_minutes_bp.route("/teams/<int:team_id>/players/<int:player_id>/edit", methods=["GET", "POST"])
@login_required
def player_edit(team_id, player_id):
    team, player = _get_player_or_404(team_id, player_id)
    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        jersey_number = request.form.get("jersey_number", "").strip() or None

        if not first_name or not last_name:
            flash("First and last name are required.", "danger")
            return render_template("basketball_minutes/player_edit.html", team=team, player=player)

        player.first_name = first_name
        player.last_name = last_name
        player.jersey_number = jersey_number
        db.session.commit()
        flash("Player updated.", "success")
        return redirect(url_for("basketball_minutes.team_detail", team_id=team.id))

    return render_template("basketball_minutes/player_edit.html", team=team, player=player)


@basketball_minutes_bp.route("/teams/<int:team_id>/players/<int:player_id>/delete", methods=["POST"])
@login_required
def player_delete(team_id, player_id):
    team, player = _get_player_or_404(team_id, player_id)
    name = player.full_name
    db.session.delete(player)
    db.session.commit()
    flash(f"Removed player {name}.", "success")
    return redirect(url_for("basketball_minutes.team_detail", team_id=team.id))


# -------------------------------------------------------------------------
# Game Endpoints (Setup, Live, Recap)
# -------------------------------------------------------------------------

@basketball_minutes_bp.route("/teams/<int:team_id>/games/new", methods=["GET", "POST"])
@login_required
def game_new(team_id):
    team = _get_team_or_404(team_id)
    if request.method == "POST":
        opponent = request.form.get("opponent_name", "").strip()
        date_str = request.form.get("game_date", "").strip()
        
        try:
            game_date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else date.today()
        except ValueError:
            game_date = date.today()

        try:
            period_count = int(request.form.get("period_count", team.default_period_count))
            if period_count not in (2, 4):
                period_count = 4
        except (ValueError, TypeError):
            period_count = 4

        try:
            period_minutes = int(request.form.get("period_minutes", team.default_period_minutes))
            if period_minutes < 1:
                period_minutes = 8
        except (ValueError, TypeError):
            period_minutes = 8

        if not opponent:
            flash("Opponent name is required.", "danger")
            return render_template("basketball_minutes/game_new.html", team=team)

        game = BkmGame.from_team_defaults(
            team=team,
            game_date=game_date,
            opponent_name=opponent,
            period_count=period_count,
            period_minutes=period_minutes,
        )
        db.session.add(game)
        db.session.commit()
        return redirect(url_for("basketball_minutes.game_detail", team_id=team.id, game_id=game.id))

    return render_template("basketball_minutes/game_new.html", team=team)


@basketball_minutes_bp.route("/teams/<int:team_id>/games/<int:game_id>")
@login_required
def game_detail(team_id, game_id):
    team, game = _get_game_or_404(team_id, game_id)
    events = ordered_events(game)
    phase = game_phase(game, events)
    
    # If game is live, redirect directly to live screen
    if phase == "live":
        return redirect(url_for("basketball_minutes.game_live", team_id=team.id, game_id=game.id))
    
    # If game is done, redirect to recap
    if phase == "done":
        return redirect(url_for("basketball_minutes.game_recap", team_id=team.id, game_id=game.id))

    # Phase is setup or between periods
    roster_with_presence = get_game_roster(game)
    present_players = [p for p, is_pres in roster_with_presence if is_pres]
    draft_lineup = list(game.draft_lineup or [])
    
    period_info = current_period_info(game, events)

    return render_template(
        "basketball_minutes/game_setup.html",
        team=team,
        game=game,
        roster=roster_with_presence,
        present_players=present_players,
        draft_lineup=draft_lineup,
        period_info=period_info,
        phase=phase,
    )


@basketball_minutes_bp.route("/teams/<int:team_id>/games/<int:game_id>/attendance", methods=["POST"])
@login_required
def game_attendance(team_id, game_id):
    team, game = _get_game_or_404(team_id, game_id)
    player_id = request.json.get("player_id") if request.is_json else request.form.get("player_id")
    is_present = request.json.get("is_present") if request.is_json else request.form.get("is_present") == "true"
    
    try:
        player_id = int(player_id)
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Invalid player id"}), 400

    entry = BkmGameRosterEntry.query.filter_by(game_id=game.id, player_id=player_id).first()
    if not entry:
        entry = BkmGameRosterEntry(game_id=game.id, player_id=player_id, is_present=bool(is_present))
        db.session.add(entry)
    else:
        entry.is_present = bool(is_present)

    # If marked absent, remove from draft lineup if there
    if not is_present and player_id in (game.draft_lineup or []):
        dl = list(game.draft_lineup)
        dl.remove(player_id)
        game.draft_lineup = dl

    db.session.commit()
    return jsonify({"success": True, "player_id": player_id, "is_present": entry.is_present})


@basketball_minutes_bp.route("/teams/<int:team_id>/games/<int:game_id>/save-draft", methods=["POST"])
@login_required
def game_save_draft(team_id, game_id):
    team, game = _get_game_or_404(team_id, game_id)
    lineup = request.json.get("lineup") if request.is_json else []
    try:
        game.draft_lineup = [int(x) for x in lineup][:5]
        db.session.commit()
        return jsonify({"success": True, "lineup": game.draft_lineup})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@basketball_minutes_bp.route("/teams/<int:team_id>/games/<int:game_id>/start-period", methods=["POST"])
@login_required
def game_start_period(team_id, game_id):
    team, game = _get_game_or_404(team_id, game_id)
    events = ordered_events(game)
    phase = game_phase(game, events)
    p_info = current_period_info(game, events)
    period_to_start = p_info["period"]

    # Lineup can come from request or game.draft_lineup
    lineup = request.json.get("lineup") if request.is_json else game.draft_lineup
    lineup = [int(x) for x in (lineup or [])]

    if len(lineup) != 5:
        return jsonify({"success": False, "error": "Exactly 5 players must be selected to start."}), 400

    # Period duration in seconds
    period_sec = game.period_minutes * 60
    if p_info["is_ot"]:
        # Overtime default or specified length
        ot_mins = request.json.get("period_minutes") if request.is_json else 4
        try:
            period_sec = int(ot_mins) * 60
        except (ValueError, TypeError):
            period_sec = 240

    game.current_period = period_to_start
    game.pending_lineup = list(lineup)

    start_event = BkmEvent(
        game_id=game.id,
        period=period_to_start,
        remaining_seconds=period_sec,
        event_type="period_start",
        payload={"lineup": lineup, "period_seconds": period_sec},
    )
    db.session.add(start_event)
    db.session.commit()

    return jsonify({"success": True, "period": period_to_start, "redirect": url_for("basketball_minutes.game_live", team_id=team.id, game_id=game.id)})


# -------------------------------------------------------------------------
# Live Game Interface & Actions
# -------------------------------------------------------------------------

@basketball_minutes_bp.route("/teams/<int:team_id>/games/<int:game_id>/live")
@login_required
def game_live(team_id, game_id):
    team, game = _get_game_or_404(team_id, game_id)
    events = ordered_events(game)
    phase = game_phase(game, events)

    if phase == "setup":
        return redirect(url_for("basketball_minutes.game_detail", team_id=team.id, game_id=game.id))
    if phase == "done":
        return redirect(url_for("basketball_minutes.game_recap", team_id=team.id, game_id=game.id))

    p_info = current_period_info(game, events)
    current_lineup = replay_lineup(events)
    
    # Players map
    players_by_id = {p.id: p for p in team.players.all()}
    roster_with_presence = get_game_roster(game)
    present_ids = {p.id for p, is_pres in roster_with_presence if is_pres}

    # Staged pending lineup
    pending = list(game.pending_lineup or current_lineup)
    
    # Bench players = present players who are not in pending
    bench_players = [
        players_by_id[pid] for pid in present_ids
        if pid in players_by_id and pid not in pending
    ]
    bench_players.sort(key=lambda p: (p.sort_order, p.id))

    on_court_players = [
        players_by_id[pid] for pid in pending
        if pid in players_by_id
    ]

    total_pts, player_stats = compute_scoring(game, events)
    stints, player_seconds, _ = compute_stints_and_minutes(game, events)

    # Attach stats to player objects for rendering
    for p in team.players.all():
        p.stats = player_stats[p.id]
        p.total_seconds = player_seconds[p.id]
        p.duration_str = format_duration(player_seconds[p.id])

    last_sec = last_event_time(game, events)

    return render_template(
        "basketball_minutes/game_live.html",
        team=team,
        game=game,
        period_info=p_info,
        on_court=on_court_players,
        bench=bench_players,
        all_players=team.players.all(),
        total_points=total_pts,
        last_remaining_sec=last_sec,
        last_remaining_formatted=format_remaining_time(last_sec),
        events=events[-10:],  # Recent 10 events for live feed
    )


@basketball_minutes_bp.route("/teams/<int:team_id>/games/<int:game_id>/sub", methods=["POST"])
@login_required
def game_sub(team_id, game_id):
    """
    Commit a substitution: takes new 5-player lineup and remaining_seconds.
    """
    team, game = _get_game_or_404(team_id, game_id)
    events = ordered_events(game)
    curr_lineup = replay_lineup(events)
    
    data = request.json or {}
    new_lineup = [int(x) for x in data.get("lineup", [])]
    raw_time = data.get("remaining_time")
    
    if len(new_lineup) != 5:
        return jsonify({"success": False, "error": "Court must have exactly 5 players."}), 400

    rem_sec = parse_time_input(raw_time, default_sec=last_event_time(game, events))
    
    subbed_on = list(set(new_lineup) - set(curr_lineup))
    subbed_off = list(set(curr_lineup) - set(new_lineup))

    sub_event = BkmEvent(
        game_id=game.id,
        period=game.current_period,
        remaining_seconds=rem_sec,
        event_type="sub",
        payload={
            "lineup": new_lineup,
            "on": subbed_on,
            "off": subbed_off,
        },
    )
    game.pending_lineup = list(new_lineup)
    db.session.add(sub_event)
    db.session.commit()

    return jsonify({"success": True, "remaining_seconds": rem_sec, "lineup": new_lineup})


@basketball_minutes_bp.route("/teams/<int:team_id>/games/<int:game_id>/score", methods=["POST"])
@login_required
def game_score(team_id, game_id):
    """
    Log a scoring event: 1pt, 2pt, 3pt, or miss_ft.
    No clock prompt required; inherits last known remaining_seconds.
    """
    team, game = _get_game_or_404(team_id, game_id)
    data = request.json or {}
    
    try:
        player_id = int(data.get("player_id"))
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Player ID required"}), 400

    shot_type = data.get("shot_type")  # '1pt', '2pt', '3pt', 'miss_ft'
    points_map = {"1pt": 1, "2pt": 2, "3pt": 3, "miss_ft": 0}
    if shot_type not in points_map:
        return jsonify({"success": False, "error": "Invalid shot type"}), 400

    rem_sec = last_event_time(game)

    score_event = BkmEvent(
        game_id=game.id,
        period=game.current_period,
        remaining_seconds=rem_sec,
        event_type="score",
        payload={
            "player_id": player_id,
            "shot_type": shot_type,
            "points": points_map[shot_type],
        },
    )
    db.session.add(score_event)
    db.session.commit()

    # Recompute total score for response
    total_pts, _ = compute_scoring(game)
    return jsonify({"success": True, "total_points": total_pts, "shot_type": shot_type, "points": points_map[shot_type]})


@basketball_minutes_bp.route("/teams/<int:team_id>/games/<int:game_id>/end-period", methods=["POST"])
@login_required
def game_end_period(team_id, game_id):
    team, game = _get_game_or_404(team_id, game_id)
    data = request.json or {}
    game_over = data.get("game_over", False)
    
    # Remaining seconds on clock at end of period (default 0)
    raw_time = data.get("remaining_time")
    rem_sec = parse_time_input(raw_time, default_sec=0)

    end_event = BkmEvent(
        game_id=game.id,
        period=game.current_period,
        remaining_seconds=rem_sec,
        event_type="period_end",
        payload={"game_over": bool(game_over)},
    )
    
    # Reset pending lineup and set draft lineup for next period to the same 5
    curr_lineup = replay_lineup(ordered_events(game))
    game.draft_lineup = list(curr_lineup)
    game.pending_lineup = None

    db.session.add(end_event)
    db.session.commit()

    if game_over or (game.current_period >= game.period_count and not data.get("add_overtime")):
        return jsonify({"success": True, "redirect": url_for("basketball_minutes.game_recap", team_id=team.id, game_id=game.id)})
    
    return jsonify({"success": True, "redirect": url_for("basketball_minutes.game_detail", team_id=team.id, game_id=game.id)})


@basketball_minutes_bp.route("/teams/<int:team_id>/games/<int:game_id>/undo", methods=["POST"])
@login_required
def game_undo(team_id, game_id):
    team, game = _get_game_or_404(team_id, game_id)
    events = ordered_events(game)
    if not events:
        return jsonify({"success": False, "error": "No events to undo"}), 400

    last_ev = events[-1]
    db.session.delete(last_ev)
    
    # Recalculate pending lineup after deletion
    remaining_events = events[:-1]
    game.pending_lineup = replay_lineup(remaining_events, game.draft_lineup)
    db.session.commit()

    return jsonify({"success": True, "undone_type": last_ev.event_type})


# -------------------------------------------------------------------------
# Game Recap & Final Score
# -------------------------------------------------------------------------

@basketball_minutes_bp.route("/teams/<int:team_id>/games/<int:game_id>/recap", methods=["GET", "POST"])
@login_required
def game_recap(team_id, game_id):
    team, game = _get_game_or_404(team_id, game_id)
    events = ordered_events(game)

    if request.method == "POST":
        our_score_raw = request.form.get("final_our_score", "").strip()
        opp_score_raw = request.form.get("final_opponent_score", "").strip()
        
        try:
            game.final_our_score = int(our_score_raw) if our_score_raw else None
        except ValueError:
            pass

        try:
            game.final_opponent_score = int(opp_score_raw) if opp_score_raw else None
        except ValueError:
            pass

        db.session.commit()
        flash("Scores saved.", "success")
        return redirect(url_for("basketball_minutes.game_recap", team_id=team.id, game_id=game.id))

    stints, player_seconds, period_player_seconds = compute_stints_and_minutes(game, events)
    tracked_points, player_stats = compute_scoring(game, events)

    # All periods played in this game
    max_period = max([e.period for e in events] + [game.period_count])
    periods_list = list(range(1, max_period + 1))

    # Compile player box score rows
    players = team.players.order_by(BkmPlayer.sort_order, BkmPlayer.id).all()
    box_score = []
    
    for p in players:
        sec = player_seconds[p.id]
        stats = player_stats[p.id]
        
        # Only show players who played or scored, or who were present
        period_breakdown = [
            format_duration(period_player_seconds.get((p.id, per), 0))
            for per in periods_list
        ]
        
        ft_att = stats["ft_att"]
        ft_made = stats["ft_made"]
        ft_pct = f"{round((ft_made / ft_att) * 100)}%" if ft_att > 0 else "-"

        box_score.append({
            "player": p,
            "total_duration": format_duration(sec),
            "total_seconds": sec,
            "period_durations": period_breakdown,
            "points": stats["points"],
            "fg2": stats["fg2_made"],
            "fg3": stats["fg3_made"],
            "ft_str": f"{ft_made}/{ft_att} ({ft_pct})" if ft_att > 0 else "0/0",
        })

    # Sort box score: players with playing time first, by minutes descending
    box_score.sort(key=lambda row: row["total_seconds"], reverse=True)

    return render_template(
        "basketball_minutes/game_recap.html",
        team=team,
        game=game,
        tracked_points=tracked_points,
        periods_list=periods_list,
        box_score=box_score,
        events=events,
    )


@basketball_minutes_bp.route("/teams/<int:team_id>/games/<int:game_id>/delete", methods=["POST"])
@login_required
def game_delete(team_id, game_id):
    team, game = _get_game_or_404(team_id, game_id)
    opp = game.opponent_name
    db.session.delete(game)
    db.session.commit()
    flash(f'Deleted game vs "{opp}".', "success")
    return redirect(url_for("basketball_minutes.team_detail", team_id=team.id))

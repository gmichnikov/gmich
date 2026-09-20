from datetime import date, datetime

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from app import db
from app.projects.soccer_minutes.clock import displayed_elapsed_ms
from app.projects.soccer_minutes.field_state import (
    drop_player_from_assignments,
    game_has_kickoff,
    present_player_ids,
    roster_entries_by_player,
    sanitize_assignments,
    set_player_present,
    setup_state,
    strip_player_from_team_games,
)
from app.projects.soccer_minutes.live_state import (
    commit_go,
    end_period,
    game_phase,
    live_payload,
    ordered_events,
    pause_clock,
    parse_action_clock,
    reset_pending,
    resume_clock,
    save_pending,
    set_clock,
    start_period,
    undo_last,
)
from app.projects.soccer_minutes.recap import event_log_rows, update_event_at_ms
from app.projects.soccer_minutes.goals import (
    apply_goal_attrs,
    create_goal,
    goal_player_options,
    goal_rows,
    ordered_goals,
    score_from_goals,
    scores_by_game_id,
    started_periods,
    validate_goal,
)
from app.projects.soccer_minutes.formation_config import (
    DEFAULT_PERIOD_COUNT,
    default_formation,
    field_size,
    line_counts,
    parse_formation_from_form,
    parse_period_count,
    pitch_bands,
)
from app.projects.soccer_minutes.models import (
    ScmEvent,
    ScmGame,
    ScmGoal,
    ScmPlayer,
    ScmTeam,
)
from app.utils.logging import log_project_visit

soccer_minutes_bp = Blueprint(
    "soccer_minutes",
    __name__,
    url_prefix="/soccer-minutes",
    template_folder="templates",
    static_folder="static",
    static_url_path="/soccer-minutes/static",
)


def _get_team_or_404(team_id):
    team = ScmTeam.query.get(team_id)
    if team is None or team.user_id != current_user.id:
        abort(404)
    return team


def _get_player_or_404(team_id, player_id):
    team = _get_team_or_404(team_id)
    player = ScmPlayer.query.filter_by(id=player_id, team_id=team.id).first()
    if player is None:
        abort(404)
    return team, player


def _get_game_or_404(team_id, game_id):
    team = _get_team_or_404(team_id)
    game = ScmGame.query.filter_by(id=game_id, team_id=team.id).first()
    if game is None:
        abort(404)
    return team, game


def _parse_game_date(raw):
    if not raw or not str(raw).strip():
        return None
    try:
        return datetime.strptime(str(raw).strip(), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _game_urls(team, game):
    kw = {"team_id": team.id, "game_id": game.id}
    return {
        "fieldUrl": url_for("soccer_minutes.game_field", **kw),
        "attendanceUrl": url_for("soccer_minutes.game_attendance", **kw),
        "pendingUrl": url_for("soccer_minutes.game_pending", **kw),
        "startUrl": url_for("soccer_minutes.game_start", **kw),
        "pauseUrl": url_for("soccer_minutes.game_pause", **kw),
        "resumeUrl": url_for("soccer_minutes.game_resume", **kw),
        "setClockUrl": url_for("soccer_minutes.game_set_clock", **kw),
        "goUrl": url_for("soccer_minutes.game_go", **kw),
        "resetUrl": url_for("soccer_minutes.game_reset", **kw),
        "endUrl": url_for("soccer_minutes.game_end", **kw),
        "undoUrl": url_for("soccer_minutes.game_undo", **kw),
        "goalUrl": url_for("soccer_minutes.game_goal_create", **kw),
    }


def _page_payload(team, game):
    payload = live_payload(team, game, urls=_game_urls(team, game))
    setup = setup_state(team, game)
    payload["attendance"] = setup["attendance"]
    payload["assignments"] = setup["assignments"]
    payload["bands"] = setup["bands"]
    payload["bench"] = setup["bench"]
    payload["filled"] = setup["filled"]
    payload["field_size"] = setup["field_size"]
    payload["locked"] = payload["phase"] not in ("setup", "between")
    _attach_goals(team, game, payload)
    return payload


def _attach_goals(team, game, payload):
    players = team.players.order_by(ScmPlayer.sort_order, ScmPlayer.id).all()
    players_by_id = {player.id: player for player in players}
    present_ids = present_player_ids(players, roster_entries_by_player(game))
    events = ordered_events(game)
    goals = ordered_goals(game)
    live_map = (payload.get("live") or {}).get("assignments") or {}
    payload["score"] = score_from_goals(goals)
    payload["goals"] = goal_rows(goals, players_by_id, events, game.formation)
    payload["goal_players"] = goal_player_options(
        players, present_ids, live_map
    )
    for row in payload["goals"]:
        row["deleteUrl"] = url_for(
            "soccer_minutes.game_goal_delete",
            team_id=team.id,
            game_id=game.id,
            goal_id=row["id"],
        )


def _json_ok(team, game, previous_phase):
    payload = _page_payload(team, game)
    payload["ok"] = True
    payload["reload"] = payload["phase"] != previous_phase
    return jsonify(payload)


def _json_error(message, status=400):
    return jsonify(ok=False, error=message), status


def _get_goal_or_404(game, goal_id):
    goal = ScmGoal.query.filter_by(id=goal_id, game_id=game.id).first()
    if goal is None:
        abort(404)
    return goal


def _goal_input():
    if request.is_json or (
        request.headers.get("Content-Type") or ""
    ).startswith("application/json"):
        return request.get_json(silent=True) or {}, True
    return request.form, False


def _recap_goals_url(team, game, anchor=None):
    url = url_for("soccer_minutes.game_recap", team_id=team.id, game_id=game.id)
    if anchor:
        return url + anchor
    return url + "#scm-goals"


def _validate_goal_from_request(team, game, data, *, live, existing=None):
    players = team.players.order_by(ScmPlayer.sort_order, ScmPlayer.id).all()
    present_ids = present_player_ids(players, roster_entries_by_player(game))
    events = ordered_events(game)
    phase = game_phase(game, events)
    displayed = displayed_elapsed_ms(game) if phase == "live" else None
    if live:
        if phase != "live":
            return "Record a goal during a period.", None
        period = game.current_period
        stamp, err = parse_action_clock(data, displayed)
        if err:
            return err, None
        if stamp is None:
            return "Enter a time like 8:00.", None
    else:
        period = data.get("period")
        stamp, err = parse_action_clock(data, None)
        if stamp is None:
            return err or "Enter a time like 8:00.", None
    require_scorer = existing is None or (
        existing.side == "us" and existing.scorer_id is not None
    )
    return validate_goal(
        side=data.get("side"),
        period=period,
        at_ms=stamp,
        scorer_id=data.get("scorer_id"),
        assist_id=data.get("assist_id"),
        events=events,
        present_ids=present_ids,
        displayed_ms=displayed,
        current_period=game.current_period,
        phase=phase,
        require_scorer=require_scorer,
    )


def _sanitize_game_maps(team, game):
    players = team.players.order_by(ScmPlayer.sort_order, ScmPlayer.id).all()
    present_ids = present_player_ids(players, roster_entries_by_player(game))
    game.draft_assignments = sanitize_assignments(
        game.formation, game.draft_assignments, present_ids
    )
    if game.pending_assignments is not None:
        game.pending_assignments = sanitize_assignments(
            game.formation, game.pending_assignments, present_ids
        )


def _next_player_sort_order(team_id):
    max_order = (
        db.session.query(func.max(ScmPlayer.sort_order))
        .filter_by(team_id=team_id)
        .scalar()
    )
    return (max_order if max_order is not None else -1) + 1


def _formation_editor_context(formation, period_count):
    counts = line_counts(formation)
    return {
        "formation_counts": counts,
        "formation_period_count": period_count,
        "formation_field_size": field_size(formation),
        "formation_bands": pitch_bands(formation),
    }


def _parse_jersey(raw):
    value = (raw or "").strip()
    if not value:
        return None
    return value[:8]


def _is_xhr():
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


def _team_roster_url(team_id):
    return url_for("soccer_minutes.team_detail", team_id=team_id) + "#scm-roster"


def _roster_list_html(team):
    players = team.players.order_by(ScmPlayer.sort_order, ScmPlayer.id).all()
    return render_template(
        "soccer_minutes/_roster_list.html",
        team=team,
        players=players,
    )


def _roster_response(team, message=None, error=None, status=200):
    if _is_xhr():
        payload = {
            "ok": error is None,
            "html": _roster_list_html(team),
        }
        if message:
            payload["message"] = message
        if error:
            payload["error"] = error
        return jsonify(payload), status
    if error:
        flash(error, "error")
    elif message:
        flash(message, "success")
    return redirect(_team_roster_url(team.id))


@soccer_minutes_bp.route("/")
@login_required
def index():
    log_project_visit("soccer_minutes", "Soccer Minutes")
    teams = (
        ScmTeam.query.filter_by(user_id=current_user.id)
        .order_by(ScmTeam.updated_at.desc())
        .all()
    )
    return render_template("soccer_minutes/index.html", teams=teams)


@soccer_minutes_bp.route("/teams/new")
@login_required
def team_new():
    return render_template("soccer_minutes/team_new.html")


@soccer_minutes_bp.route("/teams/create", methods=["POST"])
@login_required
def team_create():
    name = (request.form.get("name") or "").strip()
    season_label = (request.form.get("season_label") or "").strip() or None

    if not name:
        flash("Team name is required.", "error")
        return redirect(url_for("soccer_minutes.team_new"))

    team = ScmTeam(
        user_id=current_user.id,
        name=name,
        season_label=season_label,
        period_count=DEFAULT_PERIOD_COUNT,
        formation=default_formation(),
    )
    db.session.add(team)
    db.session.commit()

    flash(f'Team "{team.display_name}" created. Set the formation next.', "success")
    return redirect(url_for("soccer_minutes.team_edit", team_id=team.id))


@soccer_minutes_bp.route("/teams/<int:team_id>")
@login_required
def team_detail(team_id):
    team = _get_team_or_404(team_id)
    players = team.players.order_by(ScmPlayer.sort_order, ScmPlayer.id).all()
    games = team.games.order_by(ScmGame.game_date.desc(), ScmGame.id.desc()).all()
    ctx = _formation_editor_context(team.formation, team.period_count)
    return render_template(
        "soccer_minutes/team_detail.html",
        team=team,
        players=players,
        games=games,
        game_scores=scores_by_game_id([game.id for game in games]),
        **ctx,
    )


@soccer_minutes_bp.route("/teams/<int:team_id>/edit")
@login_required
def team_edit(team_id):
    team = _get_team_or_404(team_id)
    ctx = _formation_editor_context(team.formation, team.period_count)
    return render_template("soccer_minutes/team_edit.html", team=team, **ctx)


@soccer_minutes_bp.route("/teams/<int:team_id>/update", methods=["POST"])
@login_required
def team_update(team_id):
    team = _get_team_or_404(team_id)
    name = (request.form.get("name") or "").strip()
    season_label = (request.form.get("season_label") or "").strip() or None

    if not name:
        flash("Team name is required.", "error")
        return redirect(url_for("soccer_minutes.team_edit", team_id=team.id))

    team.name = name
    team.season_label = season_label
    team.period_count = parse_period_count(
        request.form.get("period_count"), team.period_count
    )
    team.formation = parse_formation_from_form(request.form, team.formation)
    team.updated_at = datetime.utcnow()
    db.session.commit()

    flash("Team settings saved.", "success")
    return redirect(url_for("soccer_minutes.team_detail", team_id=team.id))


@soccer_minutes_bp.route("/teams/<int:team_id>/delete", methods=["POST"])
@login_required
def team_delete(team_id):
    team = _get_team_or_404(team_id)
    player_count = team.players.count()
    game_count = team.games.count()
    name = team.display_name

    db.session.delete(team)
    db.session.commit()

    flash(
        f'Team "{name}" deleted ({player_count} players, {game_count} games).',
        "success",
    )
    return redirect(url_for("soccer_minutes.index"))


@soccer_minutes_bp.route("/teams/<int:team_id>/players/create", methods=["POST"])
@login_required
def player_create(team_id):
    team = _get_team_or_404(team_id)
    first_name = (request.form.get("first_name") or "").strip()
    last_name = (request.form.get("last_name") or "").strip()
    jersey_number = _parse_jersey(request.form.get("jersey_number"))

    if not first_name or not last_name:
        return _roster_response(
            team, error="First and last name are required.", status=400
        )

    player = ScmPlayer(
        team_id=team.id,
        first_name=first_name,
        last_name=last_name,
        jersey_number=jersey_number,
        sort_order=_next_player_sort_order(team.id),
    )
    db.session.add(player)
    team.updated_at = datetime.utcnow()
    db.session.commit()

    return _roster_response(team, message=f"Added {player.full_name}.")


@soccer_minutes_bp.route("/teams/<int:team_id>/players/<int:player_id>/edit")
@login_required
def player_edit(team_id, player_id):
    team, player = _get_player_or_404(team_id, player_id)
    return render_template(
        "soccer_minutes/player_edit.html",
        team=team,
        player=player,
        game_count=team.games.count(),
    )


@soccer_minutes_bp.route(
    "/teams/<int:team_id>/players/<int:player_id>/update", methods=["POST"]
)
@login_required
def player_update(team_id, player_id):
    team, player = _get_player_or_404(team_id, player_id)
    first_name = (request.form.get("first_name") or "").strip()
    last_name = (request.form.get("last_name") or "").strip()
    jersey_number = _parse_jersey(request.form.get("jersey_number"))

    if not first_name or not last_name:
        flash("First and last name are required.", "error")
        return redirect(
            url_for("soccer_minutes.player_edit", team_id=team.id, player_id=player.id)
        )

    player.first_name = first_name
    player.last_name = last_name
    player.jersey_number = jersey_number
    team.updated_at = datetime.utcnow()
    db.session.commit()

    flash("Player updated.", "success")
    return redirect(_team_roster_url(team.id))


@soccer_minutes_bp.route(
    "/teams/<int:team_id>/players/<int:player_id>/delete", methods=["POST"]
)
@login_required
def player_delete(team_id, player_id):
    team, player = _get_player_or_404(team_id, player_id)
    name = player.full_name
    game_count = team.games.count()
    strip_player_from_team_games(team, player.id)

    db.session.delete(player)
    team.updated_at = datetime.utcnow()
    db.session.commit()

    flash(
        f"Removed {name}"
        + (
            f" (also cleared from {game_count} {'game' if game_count == 1 else 'games'})."
            if game_count
            else "."
        ),
        "success",
    )
    return redirect(_team_roster_url(team.id))


@soccer_minutes_bp.route(
    "/teams/<int:team_id>/players/<int:player_id>/move-up", methods=["POST"]
)
@login_required
def player_move_up(team_id, player_id):
    team, player = _get_player_or_404(team_id, player_id)
    players = team.players.order_by(ScmPlayer.sort_order, ScmPlayer.id).all()
    index = next((i for i, item in enumerate(players) if item.id == player.id), None)
    if index is None or index == 0:
        return _roster_response(team)

    neighbor = players[index - 1]
    player.sort_order, neighbor.sort_order = neighbor.sort_order, player.sort_order
    team.updated_at = datetime.utcnow()
    db.session.commit()
    return _roster_response(team)


@soccer_minutes_bp.route(
    "/teams/<int:team_id>/players/<int:player_id>/move-down", methods=["POST"]
)
@login_required
def player_move_down(team_id, player_id):
    team, player = _get_player_or_404(team_id, player_id)
    players = team.players.order_by(ScmPlayer.sort_order, ScmPlayer.id).all()
    index = next((i for i, item in enumerate(players) if item.id == player.id), None)
    if index is None or index >= len(players) - 1:
        return _roster_response(team)

    neighbor = players[index + 1]
    player.sort_order, neighbor.sort_order = neighbor.sort_order, player.sort_order
    team.updated_at = datetime.utcnow()
    db.session.commit()
    return _roster_response(team)


@soccer_minutes_bp.route("/teams/<int:team_id>/games/new")
@login_required
def game_new(team_id):
    team = _get_team_or_404(team_id)
    return render_template(
        "soccer_minutes/game_new.html",
        team=team,
        field_size=field_size(team.formation),
        default_date=date.today().isoformat(),
    )


@soccer_minutes_bp.route("/teams/<int:team_id>/games/create", methods=["POST"])
@login_required
def game_create(team_id):
    team = _get_team_or_404(team_id)
    opponent_name = (request.form.get("opponent_name") or "").strip()[:120]
    game_date = _parse_game_date(request.form.get("game_date"))

    if not opponent_name:
        flash("Opponent name is required.", "error")
        return redirect(url_for("soccer_minutes.game_new", team_id=team.id))
    if game_date is None:
        flash("A valid game date is required.", "error")
        return redirect(url_for("soccer_minutes.game_new", team_id=team.id))

    game = ScmGame.from_team_defaults(team, game_date, opponent_name)
    db.session.add(game)
    team.updated_at = datetime.utcnow()
    db.session.commit()

    flash(f"Game vs {opponent_name} created.", "success")
    return redirect(
        url_for("soccer_minutes.game_detail", team_id=team.id, game_id=game.id)
    )


@soccer_minutes_bp.route("/teams/<int:team_id>/games/<int:game_id>")
@login_required
def game_detail(team_id, game_id):
    team, game = _get_game_or_404(team_id, game_id)
    payload = _page_payload(team, game)
    template = (
        "soccer_minutes/game_live.html"
        if payload["phase"] == "live"
        else "soccer_minutes/game_detail.html"
    )
    return render_template(
        template,
        team=team,
        game=game,
        setup=payload,
        live=payload,
    )


@soccer_minutes_bp.route("/teams/<int:team_id>/games/<int:game_id>/recap")
@login_required
def game_recap(team_id, game_id):
    team, game = _get_game_or_404(team_id, game_id)
    payload = _page_payload(team, game)
    players = team.players.order_by(ScmPlayer.sort_order, ScmPlayer.id).all()
    players_by_id = {player.id: player for player in players}
    events = event_log_rows(ordered_events(game), game.formation, players_by_id)
    return render_template(
        "soccer_minutes/game_recap.html",
        team=team,
        game=game,
        minutes=payload["minutes"],
        events=events,
        phase=payload["phase"],
        score=payload["score"],
        goals=payload["goals"],
        goal_players=payload["goal_players"],
        started_periods=started_periods(ordered_events(game)),
        default_goal_period=game.current_period,
        default_goal_clock=payload["clock"]["displayed"]
        if payload["phase"] == "live"
        else "",
    )


@soccer_minutes_bp.route(
    "/teams/<int:team_id>/games/<int:game_id>/events/<int:event_id>/time",
    methods=["POST"],
)
@login_required
def event_set_time(team_id, game_id, event_id):
    team, game = _get_game_or_404(team_id, game_id)
    event = ScmEvent.query.filter_by(id=event_id, game_id=game.id).first()
    if event is None:
        abort(404)
    recap_url = url_for(
        "soccer_minutes.game_recap", team_id=team.id, game_id=game.id
    ) + f"#scm-event-{event.id}"
    stamp, err = parse_action_clock({"clock": request.form.get("clock")}, None)
    if stamp is None:
        flash(err or "Enter a time like 8:00.", "error")
        return redirect(recap_url)
    error = update_event_at_ms(game, event.id, stamp)
    if error:
        flash(error, "error")
        return redirect(recap_url)
    db.session.commit()
    flash("Event time saved.", "success")
    return redirect(recap_url)


@soccer_minutes_bp.route(
    "/teams/<int:team_id>/games/<int:game_id>/goals", methods=["POST"]
)
@login_required
def game_goal_create(team_id, game_id):
    team, game = _get_game_or_404(team_id, game_id)
    data, live = _goal_input()
    previous = game_phase(game)
    error, attrs = _validate_goal_from_request(team, game, data, live=live)
    if error:
        if live:
            return _json_error(error)
        flash(error, "error")
        return redirect(_recap_goals_url(team, game, "#scm-goal-add"))
    goal = create_goal(game, attrs)
    db.session.add(goal)
    db.session.commit()
    if live:
        return _json_ok(team, game, previous)
    flash("Goal saved.", "success")
    return redirect(_recap_goals_url(team, game, f"#scm-goal-{goal.id}"))


@soccer_minutes_bp.route(
    "/teams/<int:team_id>/games/<int:game_id>/goals/<int:goal_id>/update",
    methods=["POST"],
)
@login_required
def game_goal_update(team_id, game_id, goal_id):
    team, game = _get_game_or_404(team_id, game_id)
    goal = _get_goal_or_404(game, goal_id)
    recap_url = _recap_goals_url(team, game, f"#scm-goal-{goal.id}")
    data = request.form
    error, attrs = _validate_goal_from_request(
        team, game, data, live=False, existing=goal
    )
    if error:
        flash(error, "error")
        return redirect(recap_url)
    apply_goal_attrs(goal, attrs)
    game.updated_at = datetime.utcnow()
    db.session.commit()
    flash("Goal saved.", "success")
    return redirect(recap_url)


@soccer_minutes_bp.route(
    "/teams/<int:team_id>/games/<int:game_id>/goals/<int:goal_id>/delete",
    methods=["POST"],
)
@login_required
def game_goal_delete(team_id, game_id, goal_id):
    team, game = _get_game_or_404(team_id, game_id)
    goal = _get_goal_or_404(game, goal_id)
    _data, live = _goal_input()
    previous = game_phase(game)
    db.session.delete(goal)
    game.updated_at = datetime.utcnow()
    db.session.commit()
    if live:
        return _json_ok(team, game, previous)
    flash("Goal removed.", "success")
    return redirect(_recap_goals_url(team, game))


@soccer_minutes_bp.route("/teams/<int:team_id>/games/<int:game_id>/edit")
@login_required
def game_edit(team_id, game_id):
    team, game = _get_game_or_404(team_id, game_id)
    ctx = _formation_editor_context(game.formation, game.period_count)
    return render_template(
        "soccer_minutes/game_edit.html",
        team=team,
        game=game,
        locked=game_has_kickoff(game),
        **ctx,
    )


@soccer_minutes_bp.route(
    "/teams/<int:team_id>/games/<int:game_id>/update", methods=["POST"]
)
@login_required
def game_update(team_id, game_id):
    team, game = _get_game_or_404(team_id, game_id)
    opponent_name = (request.form.get("opponent_name") or "").strip()[:120]
    game_date = _parse_game_date(request.form.get("game_date"))
    locked = game_has_kickoff(game)

    if not opponent_name:
        flash("Opponent name is required.", "error")
        return redirect(
            url_for("soccer_minutes.game_edit", team_id=team.id, game_id=game.id)
        )
    if game_date is None:
        flash("A valid game date is required.", "error")
        return redirect(
            url_for("soccer_minutes.game_edit", team_id=team.id, game_id=game.id)
        )

    game.opponent_name = opponent_name
    game.game_date = game_date
    if not locked:
        game.period_count = parse_period_count(
            request.form.get("period_count"), game.period_count
        )
        game.formation = parse_formation_from_form(request.form, game.formation)
        _sanitize_game_maps(team, game)
    game.updated_at = datetime.utcnow()
    team.updated_at = datetime.utcnow()
    db.session.commit()

    flash("Game settings saved.", "success")
    return redirect(
        url_for("soccer_minutes.game_detail", team_id=team.id, game_id=game.id)
    )


@soccer_minutes_bp.route(
    "/teams/<int:team_id>/games/<int:game_id>/delete", methods=["POST"]
)
@login_required
def game_delete(team_id, game_id):
    team, game = _get_game_or_404(team_id, game_id)
    opponent_name = game.opponent_name

    db.session.delete(game)
    team.updated_at = datetime.utcnow()
    db.session.commit()

    flash(f"Deleted game vs {opponent_name}.", "success")
    return redirect(url_for("soccer_minutes.team_detail", team_id=team.id))


@soccer_minutes_bp.route(
    "/teams/<int:team_id>/games/<int:game_id>/attendance", methods=["POST"]
)
@login_required
def game_attendance(team_id, game_id):
    team, game = _get_game_or_404(team_id, game_id)
    data = request.get_json(silent=True) or {}
    try:
        player_id = int(data.get("player_id"))
    except (TypeError, ValueError):
        return jsonify(ok=False, error="Player is required."), 400

    player = ScmPlayer.query.filter_by(id=player_id, team_id=team.id).first()
    if player is None:
        return jsonify(ok=False, error="Player not found."), 404

    present = data.get("present")
    if isinstance(present, str):
        present = present.lower() in ("1", "true", "yes")
    present = bool(present)

    set_player_present(game, player, present)
    if not present:
        game.draft_assignments = drop_player_from_assignments(
            game.draft_assignments, player.id
        )
        if game.pending_assignments is not None:
            game.pending_assignments = drop_player_from_assignments(
                game.pending_assignments, player.id
            )
    game.updated_at = datetime.utcnow()
    db.session.commit()

    payload = _page_payload(team, game)
    payload["ok"] = True
    return jsonify(payload)


@soccer_minutes_bp.route(
    "/teams/<int:team_id>/games/<int:game_id>/field", methods=["POST"]
)
@login_required
def game_field(team_id, game_id):
    team, game = _get_game_or_404(team_id, game_id)
    if game_phase(game) not in ("setup", "between"):
        return _json_error("Edit the pending field during a period.")

    data = request.get_json(silent=True) or {}
    assignments = data.get("assignments")
    if not isinstance(assignments, dict):
        return jsonify(ok=False, error="Invalid field assignments."), 400

    players = team.players.order_by(ScmPlayer.sort_order, ScmPlayer.id).all()
    present_ids = present_player_ids(players, roster_entries_by_player(game))
    game.draft_assignments = sanitize_assignments(
        game.formation, assignments, present_ids
    )
    game.updated_at = datetime.utcnow()
    db.session.commit()

    payload = _page_payload(team, game)
    payload["ok"] = True
    return jsonify(payload)


@soccer_minutes_bp.route(
    "/teams/<int:team_id>/games/<int:game_id>/start", methods=["POST"]
)
@login_required
def game_start(team_id, game_id):
    team, game = _get_game_or_404(team_id, game_id)
    previous = game_phase(game)
    error = start_period(team, game)
    if error:
        return _json_error(error)
    db.session.commit()
    return _json_ok(team, game, previous)


@soccer_minutes_bp.route(
    "/teams/<int:team_id>/games/<int:game_id>/pause", methods=["POST"]
)
@login_required
def game_pause(team_id, game_id):
    team, game = _get_game_or_404(team_id, game_id)
    previous = game_phase(game)
    error = pause_clock(game)
    if error:
        return _json_error(error)
    db.session.commit()
    return _json_ok(team, game, previous)


@soccer_minutes_bp.route(
    "/teams/<int:team_id>/games/<int:game_id>/resume", methods=["POST"]
)
@login_required
def game_resume(team_id, game_id):
    team, game = _get_game_or_404(team_id, game_id)
    previous = game_phase(game)
    error = resume_clock(game)
    if error:
        return _json_error(error)
    db.session.commit()
    return _json_ok(team, game, previous)


@soccer_minutes_bp.route(
    "/teams/<int:team_id>/games/<int:game_id>/set-clock", methods=["POST"]
)
@login_required
def game_set_clock(team_id, game_id):
    team, game = _get_game_or_404(team_id, game_id)
    previous = game_phase(game)
    data = request.get_json(silent=True) or {}
    stamp, err = parse_action_clock(data, None)
    if stamp is None:
        return _json_error(err or "Enter a time like 5:00.")
    error = set_clock(game, stamp)
    if error:
        return _json_error(error)
    db.session.commit()
    return _json_ok(team, game, previous)


@soccer_minutes_bp.route(
    "/teams/<int:team_id>/games/<int:game_id>/pending", methods=["POST"]
)
@login_required
def game_pending(team_id, game_id):
    team, game = _get_game_or_404(team_id, game_id)
    previous = game_phase(game)
    data = request.get_json(silent=True) or {}
    error = save_pending(team, game, data.get("assignments"))
    if error:
        return _json_error(error)
    db.session.commit()
    return _json_ok(team, game, previous)


@soccer_minutes_bp.route(
    "/teams/<int:team_id>/games/<int:game_id>/reset", methods=["POST"]
)
@login_required
def game_reset(team_id, game_id):
    team, game = _get_game_or_404(team_id, game_id)
    previous = game_phase(game)
    error = reset_pending(team, game)
    if error:
        return _json_error(error)
    db.session.commit()
    return _json_ok(team, game, previous)


@soccer_minutes_bp.route(
    "/teams/<int:team_id>/games/<int:game_id>/go", methods=["POST"]
)
@login_required
def game_go(team_id, game_id):
    team, game = _get_game_or_404(team_id, game_id)
    previous = game_phase(game)
    data = request.get_json(silent=True) or {}
    stamp, err = parse_action_clock(data, displayed_elapsed_ms(game))
    if err:
        return _json_error(err)
    error = commit_go(team, game, at_ms=stamp)
    if error:
        return _json_error(error)
    db.session.commit()
    return _json_ok(team, game, previous)


@soccer_minutes_bp.route(
    "/teams/<int:team_id>/games/<int:game_id>/end", methods=["POST"]
)
@login_required
def game_end(team_id, game_id):
    team, game = _get_game_or_404(team_id, game_id)
    previous = game_phase(game)
    error = end_period(game, team)
    if error:
        return _json_error(error)
    db.session.commit()
    return _json_ok(team, game, previous)


@soccer_minutes_bp.route(
    "/teams/<int:team_id>/games/<int:game_id>/undo", methods=["POST"]
)
@login_required
def game_undo(team_id, game_id):
    team, game = _get_game_or_404(team_id, game_id)
    previous = game_phase(game)
    error = undo_last(game)
    if error:
        return _json_error(error)
    db.session.commit()
    return _json_ok(team, game, previous)

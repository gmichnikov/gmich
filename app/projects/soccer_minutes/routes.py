from datetime import date, datetime

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from app import db
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
from app.projects.soccer_minutes.formation_config import (
    DEFAULT_PERIOD_COUNT,
    default_formation,
    field_size,
    line_counts,
    parse_formation_from_form,
    parse_period_count,
    pitch_bands,
)
from app.projects.soccer_minutes.models import ScmGame, ScmPlayer, ScmTeam
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


def _setup_payload(team, game):
    payload = setup_state(team, game)
    payload["fieldUrl"] = url_for(
        "soccer_minutes.game_field", team_id=team.id, game_id=game.id
    )
    payload["attendanceUrl"] = url_for(
        "soccer_minutes.game_attendance", team_id=team.id, game_id=game.id
    )
    return payload


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
    return render_template(
        "soccer_minutes/game_detail.html",
        team=team,
        game=game,
        setup=_setup_payload(team, game),
    )


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

    payload = _setup_payload(team, game)
    payload["ok"] = True
    return jsonify(payload)


@soccer_minutes_bp.route(
    "/teams/<int:team_id>/games/<int:game_id>/field", methods=["POST"]
)
@login_required
def game_field(team_id, game_id):
    team, game = _get_game_or_404(team_id, game_id)
    if game_has_kickoff(game):
        return jsonify(ok=False, error="The field is locked after kickoff."), 400

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

    payload = _setup_payload(team, game)
    payload["ok"] = True
    return jsonify(payload)

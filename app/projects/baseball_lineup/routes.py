from datetime import date, datetime

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from app import db
from app.projects.baseball_lineup.lineup_config import (
    BATTERY_CODES,
    EDITOR_FIELD_CODES,
    LABEL_BY_CODE,
    default_expected_counts,
    field_spots_by_inning,
    normalize_expected_counts,
    parse_expected_counts_from_form,
    parse_inning_count,
    resize_expected_counts,
)
from app.projects.baseball_lineup.models import (
    BluGame,
    BluGameRosterEntry,
    BluLineupCell,
    BluPlayer,
    BluTeam,
)
from app.projects.baseball_lineup.lineup_grid import (
    batting_order_rows,
    build_lineup_rows,
    compute_inning_warnings,
    lineup_editor_payload,
    load_cells_by_player,
    move_batting_order,
    present_players_for_game,
    randomize_batting_order,
    save_lineup_cells,
)
from app.utils.logging import log_project_visit

baseball_lineup_bp = Blueprint(
    "baseball_lineup",
    __name__,
    url_prefix="/baseball-lineup",
    template_folder="templates",
    static_folder="static",
    static_url_path="/baseball-lineup/static",
)


def _get_team_or_404(team_id):
    team = BluTeam.query.get(team_id)
    if team is None or team.user_id != current_user.id:
        abort(404)
    return team


def _get_player_or_404(team_id, player_id):
    team = _get_team_or_404(team_id)
    player = BluPlayer.query.filter_by(id=player_id, team_id=team.id).first()
    if player is None:
        abort(404)
    return team, player


def _next_player_sort_order(team_id):
    max_order = (
        db.session.query(func.max(BluPlayer.sort_order))
        .filter_by(team_id=team_id)
        .scalar()
    )
    return (max_order if max_order is not None else -1) + 1


def _player_game_count(player_id):
    return (
        db.session.query(func.count(func.distinct(BluLineupCell.game_id)))
        .filter(BluLineupCell.player_id == player_id)
        .scalar()
        or 0
    )


def _structure_editor_context(expected_counts, inning_count):
    counts = normalize_expected_counts(expected_counts, inning_count)
    return {
        "structure_codes": EDITOR_FIELD_CODES,
        "structure_labels": LABEL_BY_CODE,
        "structure_battery_codes": BATTERY_CODES,
        "structure_counts": counts,
        "structure_inning_count": inning_count,
        "structure_field_spots": field_spots_by_inning(counts, inning_count),
    }


def _parse_team_structure_form(form, current_counts, current_inning_count):
    return _parse_structure_form(form, current_counts, current_inning_count)


def _parse_structure_form(form, current_counts, current_inning_count):
    inning_count = parse_inning_count(
        form.get("inning_count"), default=current_inning_count
    )
    resized = resize_expected_counts(current_counts or {}, inning_count)
    counts = parse_expected_counts_from_form(form, inning_count)
    for code in EDITOR_FIELD_CODES:
        if code not in counts:
            counts[code] = resized.get(code, [0] * inning_count)
    return inning_count, counts


def _parse_game_date(raw):
    if not raw or not str(raw).strip():
        return None
    try:
        return datetime.strptime(str(raw).strip(), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _get_game_or_404(team_id, game_id):
    team = _get_team_or_404(team_id)
    game = BluGame.query.filter_by(id=game_id, team_id=team.id).first()
    if game is None:
        abort(404)
    return team, game


def _game_roster_status(game, team):
    """Return roster players with present/absent status for a game."""
    players = team.players.order_by(BluPlayer.sort_order, BluPlayer.id).all()
    absent_ids = {
        entry.player_id
        for entry in game.roster_entries.filter_by(is_present=False).all()
    }
    return [
        {"player": player, "is_present": player.id not in absent_ids}
        for player in players
    ]


def _set_player_present(game, player, present):
    entry = BluGameRosterEntry.query.filter_by(
        game_id=game.id, player_id=player.id
    ).first()
    if present:
        if entry is None:
            return
        if entry.batting_order is None:
            db.session.delete(entry)
        else:
            entry.is_present = True
    elif entry is None:
        db.session.add(
            BluGameRosterEntry(
                game_id=game.id,
                player_id=player.id,
                is_present=False,
            )
        )
    else:
        entry.is_present = False


@baseball_lineup_bp.route("/")
@login_required
def index():
    log_project_visit("baseball_lineup", "Baseball Lineup")
    teams = (
        BluTeam.query.filter_by(user_id=current_user.id)
        .order_by(BluTeam.updated_at.desc())
        .all()
    )
    return render_template("baseball_lineup/index.html", teams=teams)


@baseball_lineup_bp.route("/teams/new")
@login_required
def team_new():
    return render_template("baseball_lineup/team_new.html")


@baseball_lineup_bp.route("/teams/create", methods=["POST"])
@login_required
def team_create():
    name = (request.form.get("name") or "").strip()
    season_label = (request.form.get("season_label") or "").strip() or None

    if not name:
        flash("Team name is required.", "error")
        return redirect(url_for("baseball_lineup.team_new"))

    team = BluTeam(
        user_id=current_user.id,
        name=name,
        season_label=season_label,
        default_inning_count=6,
        default_expected_counts=default_expected_counts(),
    )
    db.session.add(team)
    db.session.commit()

    flash(f'Team "{team.display_name}" created.', "success")
    return redirect(url_for("baseball_lineup.team_edit", team_id=team.id))


@baseball_lineup_bp.route("/teams/<int:team_id>")
@login_required
def team_detail(team_id):
    team = _get_team_or_404(team_id)
    players = team.players.order_by(BluPlayer.sort_order, BluPlayer.id).all()
    games = team.games.order_by(BluGame.game_date.desc(), BluGame.id.desc()).all()
    return render_template(
        "baseball_lineup/team_detail.html",
        team=team,
        players=players,
        games=games,
    )


@baseball_lineup_bp.route("/teams/<int:team_id>/edit")
@login_required
def team_edit(team_id):
    team = _get_team_or_404(team_id)
    ctx = _structure_editor_context(
        team.default_expected_counts, team.default_inning_count
    )
    return render_template("baseball_lineup/team_edit.html", team=team, **ctx)


@baseball_lineup_bp.route("/teams/<int:team_id>/update", methods=["POST"])
@login_required
def team_update(team_id):
    team = _get_team_or_404(team_id)
    name = (request.form.get("name") or "").strip()
    season_label = (request.form.get("season_label") or "").strip() or None

    if not name:
        flash("Team name is required.", "error")
        return redirect(url_for("baseball_lineup.team_edit", team_id=team.id))

    inning_count, counts = _parse_team_structure_form(
        request.form,
        team.default_expected_counts,
        team.default_inning_count,
    )

    team.name = name
    team.season_label = season_label
    team.default_inning_count = inning_count
    team.default_expected_counts = counts
    team.updated_at = datetime.utcnow()
    db.session.commit()

    flash("Team settings saved.", "success")
    return redirect(url_for("baseball_lineup.team_detail", team_id=team.id))


@baseball_lineup_bp.route("/teams/<int:team_id>/delete", methods=["POST"])
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
    return redirect(url_for("baseball_lineup.index"))


@baseball_lineup_bp.route("/teams/<int:team_id>/players/create", methods=["POST"])
@login_required
def player_create(team_id):
    team = _get_team_or_404(team_id)
    first_name = (request.form.get("first_name") or "").strip()
    last_name = (request.form.get("last_name") or "").strip()

    if not first_name or not last_name:
        flash("First and last name are required.", "error")
        return redirect(url_for("baseball_lineup.team_detail", team_id=team.id))

    player = BluPlayer(
        team_id=team.id,
        first_name=first_name,
        last_name=last_name,
        sort_order=_next_player_sort_order(team.id),
    )
    db.session.add(player)
    team.updated_at = datetime.utcnow()
    db.session.commit()

    flash(f"Added {player.full_name}.", "success")
    return redirect(url_for("baseball_lineup.team_detail", team_id=team.id))


@baseball_lineup_bp.route("/teams/<int:team_id>/players/<int:player_id>/edit")
@login_required
def player_edit(team_id, player_id):
    team, player = _get_player_or_404(team_id, player_id)
    return render_template(
        "baseball_lineup/player_edit.html",
        team=team,
        player=player,
        game_count=_player_game_count(player.id),
    )


@baseball_lineup_bp.route(
    "/teams/<int:team_id>/players/<int:player_id>/update", methods=["POST"]
)
@login_required
def player_update(team_id, player_id):
    team, player = _get_player_or_404(team_id, player_id)
    first_name = (request.form.get("first_name") or "").strip()
    last_name = (request.form.get("last_name") or "").strip()

    if not first_name or not last_name:
        flash("First and last name are required.", "error")
        return redirect(
            url_for("baseball_lineup.player_edit", team_id=team.id, player_id=player.id)
        )

    player.first_name = first_name
    player.last_name = last_name
    team.updated_at = datetime.utcnow()
    db.session.commit()

    flash("Player updated.", "success")
    return redirect(url_for("baseball_lineup.team_detail", team_id=team.id))


@baseball_lineup_bp.route(
    "/teams/<int:team_id>/players/<int:player_id>/delete", methods=["POST"]
)
@login_required
def player_delete(team_id, player_id):
    team, player = _get_player_or_404(team_id, player_id)
    name = player.full_name
    game_count = _player_game_count(player.id)

    db.session.delete(player)
    team.updated_at = datetime.utcnow()
    db.session.commit()

    flash(
        f'Removed {name}'
        + (f" (lineup data in {game_count} games also deleted)." if game_count else "."),
        "success",
    )
    return redirect(url_for("baseball_lineup.team_detail", team_id=team.id))


@baseball_lineup_bp.route(
    "/teams/<int:team_id>/players/<int:player_id>/move-up", methods=["POST"]
)
@login_required
def player_move_up(team_id, player_id):
    team, player = _get_player_or_404(team_id, player_id)
    players = team.players.order_by(BluPlayer.sort_order, BluPlayer.id).all()
    index = next((i for i, p in enumerate(players) if p.id == player.id), None)
    if index is None or index == 0:
        return redirect(url_for("baseball_lineup.team_detail", team_id=team.id))

    neighbor = players[index - 1]
    player.sort_order, neighbor.sort_order = neighbor.sort_order, player.sort_order
    team.updated_at = datetime.utcnow()
    db.session.commit()
    return redirect(url_for("baseball_lineup.team_detail", team_id=team.id))


@baseball_lineup_bp.route(
    "/teams/<int:team_id>/players/<int:player_id>/move-down", methods=["POST"]
)
@login_required
def player_move_down(team_id, player_id):
    team, player = _get_player_or_404(team_id, player_id)
    players = team.players.order_by(BluPlayer.sort_order, BluPlayer.id).all()
    index = next((i for i, p in enumerate(players) if p.id == player.id), None)
    if index is None or index >= len(players) - 1:
        return redirect(url_for("baseball_lineup.team_detail", team_id=team.id))

    neighbor = players[index + 1]
    player.sort_order, neighbor.sort_order = neighbor.sort_order, player.sort_order
    team.updated_at = datetime.utcnow()
    db.session.commit()
    return redirect(url_for("baseball_lineup.team_detail", team_id=team.id))


@baseball_lineup_bp.route("/teams/<int:team_id>/games/new")
@login_required
def game_new(team_id):
    team = _get_team_or_404(team_id)
    return render_template(
        "baseball_lineup/game_new.html",
        team=team,
        default_date=date.today().isoformat(),
    )


@baseball_lineup_bp.route("/teams/<int:team_id>/games/create", methods=["POST"])
@login_required
def game_create(team_id):
    team = _get_team_or_404(team_id)
    opponent_name = (request.form.get("opponent_name") or "").strip()
    game_date = _parse_game_date(request.form.get("game_date"))

    if not opponent_name:
        flash("Opponent name is required.", "error")
        return redirect(url_for("baseball_lineup.game_new", team_id=team.id))
    if game_date is None:
        flash("A valid game date is required.", "error")
        return redirect(url_for("baseball_lineup.game_new", team_id=team.id))

    game = BluGame.from_team_defaults(team, game_date, opponent_name)
    db.session.add(game)
    team.updated_at = datetime.utcnow()
    db.session.commit()

    flash(f"Game vs {opponent_name} created.", "success")
    return redirect(
        url_for("baseball_lineup.game_detail", team_id=team.id, game_id=game.id)
    )


def _lineup_view_context(game, team):
    present_players = present_players_for_game(game, team)
    player_ids = [player.id for player in present_players]
    cells_by_player = load_cells_by_player(game, player_ids)
    lineup_rows = build_lineup_rows(game, present_players, cells_by_player)
    warnings = compute_inning_warnings(game, present_players, cells_by_player)
    return {
        "present_players": present_players,
        "lineup_rows": lineup_rows,
        "lineup_warnings": warnings,
    }


@baseball_lineup_bp.route("/teams/<int:team_id>/games/<int:game_id>")
@login_required
def game_detail(team_id, game_id):
    team, game = _get_game_or_404(team_id, game_id)
    roster_status = _game_roster_status(game, team)
    present_count = sum(1 for row in roster_status if row["is_present"])
    lineup_ctx = _lineup_view_context(game, team)
    return render_template(
        "baseball_lineup/game_detail.html",
        team=team,
        game=game,
        roster_status=roster_status,
        present_count=present_count,
        batting_order_rows=batting_order_rows(game, team),
        **lineup_ctx,
    )


@baseball_lineup_bp.route("/teams/<int:team_id>/games/<int:game_id>/edit")
@login_required
def game_edit(team_id, game_id):
    team, game = _get_game_or_404(team_id, game_id)
    ctx = _structure_editor_context(game.expected_counts, game.inning_count)
    return render_template(
        "baseball_lineup/game_edit.html",
        team=team,
        game=game,
        **ctx,
    )


@baseball_lineup_bp.route(
    "/teams/<int:team_id>/games/<int:game_id>/update", methods=["POST"]
)
@login_required
def game_update(team_id, game_id):
    team, game = _get_game_or_404(team_id, game_id)
    opponent_name = (request.form.get("opponent_name") or "").strip()
    game_date = _parse_game_date(request.form.get("game_date"))

    if not opponent_name:
        flash("Opponent name is required.", "error")
        return redirect(
            url_for("baseball_lineup.game_edit", team_id=team.id, game_id=game.id)
        )
    if game_date is None:
        flash("A valid game date is required.", "error")
        return redirect(
            url_for("baseball_lineup.game_edit", team_id=team.id, game_id=game.id)
        )

    inning_count, counts = _parse_structure_form(
        request.form,
        game.expected_counts,
        game.inning_count,
    )

    game.game_date = game_date
    game.opponent_name = opponent_name
    game.inning_count = inning_count
    game.expected_counts = counts
    game.updated_at = datetime.utcnow()
    team.updated_at = datetime.utcnow()
    db.session.commit()

    flash("Game settings saved.", "success")
    return redirect(
        url_for("baseball_lineup.game_detail", team_id=team.id, game_id=game.id)
    )


@baseball_lineup_bp.route(
    "/teams/<int:team_id>/games/<int:game_id>/delete", methods=["POST"]
)
@login_required
def game_delete(team_id, game_id):
    team, game = _get_game_or_404(team_id, game_id)
    label = f"{game.game_date.strftime('%b %d, %Y')} vs {game.opponent_name}"

    db.session.delete(game)
    team.updated_at = datetime.utcnow()
    db.session.commit()

    flash(f"Deleted {label}.", "success")
    return redirect(url_for("baseball_lineup.team_detail", team_id=team.id))


@baseball_lineup_bp.route(
    "/teams/<int:team_id>/games/<int:game_id>/attendance/<int:player_id>/toggle",
    methods=["POST"],
)
@login_required
def game_attendance_toggle(team_id, game_id, player_id):
    team, game = _get_game_or_404(team_id, game_id)
    _, player = _get_player_or_404(team_id, player_id)

    entry = BluGameRosterEntry.query.filter_by(
        game_id=game.id, player_id=player.id
    ).first()
    currently_present = entry is None or entry.is_present
    _set_player_present(game, player, present=not currently_present)

    game.updated_at = datetime.utcnow()
    team.updated_at = datetime.utcnow()
    db.session.commit()

    status = "present" if not currently_present else "absent"
    flash(f"Marked {player.full_name} {status}.", "success")
    return redirect(
        url_for("baseball_lineup.game_detail", team_id=team.id, game_id=game.id)
    )


@baseball_lineup_bp.route("/teams/<int:team_id>/games/<int:game_id>/lineup")
@login_required
def game_lineup_edit(team_id, game_id):
    team, game = _get_game_or_404(team_id, game_id)
    present_players = present_players_for_game(game, team)
    if not present_players:
        flash("Add players and mark attendance before editing the lineup.", "error")
        return redirect(
            url_for("baseball_lineup.game_detail", team_id=team.id, game_id=game.id)
        )

    payload = lineup_editor_payload(game, team)
    return render_template(
        "baseball_lineup/game_lineup_edit.html",
        team=team,
        game=game,
        lineup_payload=payload,
        save_url=url_for(
            "baseball_lineup.game_lineup_save", team_id=team.id, game_id=game.id
        ),
        cancel_url=url_for(
            "baseball_lineup.game_detail", team_id=team.id, game_id=game.id
        ),
    )


@baseball_lineup_bp.route(
    "/teams/<int:team_id>/games/<int:game_id>/lineup/save", methods=["POST"]
)
@login_required
def game_lineup_save(team_id, game_id):
    team, game = _get_game_or_404(team_id, game_id)
    data = request.get_json(silent=True) or {}
    cells = data.get("cells")
    if not isinstance(cells, list):
        return jsonify({"ok": False, "error": "Invalid lineup data."}), 400

    present_players = present_players_for_game(game, team)
    present_ids = [player.id for player in present_players]

    save_lineup_cells(game, present_ids, cells)
    game.updated_at = datetime.utcnow()
    team.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify(
        {
            "ok": True,
            "redirect": url_for(
                "baseball_lineup.game_detail", team_id=team.id, game_id=game.id
            ),
        }
    )


@baseball_lineup_bp.route(
    "/teams/<int:team_id>/games/<int:game_id>/batting-order/<int:player_id>/move-up",
    methods=["POST"],
)
@login_required
def game_batting_order_move_up(team_id, game_id, player_id):
    team, game = _get_game_or_404(team_id, game_id)
    _, player = _get_player_or_404(team_id, player_id)
    move_batting_order(game, team, player.id, "up")
    game.updated_at = datetime.utcnow()
    team.updated_at = datetime.utcnow()
    db.session.commit()
    return redirect(
        url_for("baseball_lineup.game_detail", team_id=team.id, game_id=game.id)
    )


@baseball_lineup_bp.route(
    "/teams/<int:team_id>/games/<int:game_id>/batting-order/<int:player_id>/move-down",
    methods=["POST"],
)
@login_required
def game_batting_order_move_down(team_id, game_id, player_id):
    team, game = _get_game_or_404(team_id, game_id)
    _, player = _get_player_or_404(team_id, player_id)
    move_batting_order(game, team, player.id, "down")
    game.updated_at = datetime.utcnow()
    team.updated_at = datetime.utcnow()
    db.session.commit()
    return redirect(
        url_for("baseball_lineup.game_detail", team_id=team.id, game_id=game.id)
    )


@baseball_lineup_bp.route(
    "/teams/<int:team_id>/games/<int:game_id>/batting-order/randomize",
    methods=["POST"],
)
@login_required
def game_batting_order_randomize(team_id, game_id):
    team, game = _get_game_or_404(team_id, game_id)
    randomize_batting_order(game, team)
    game.updated_at = datetime.utcnow()
    team.updated_at = datetime.utcnow()
    db.session.commit()
    flash("Batting order randomized.", "success")
    return redirect(
        url_for("baseball_lineup.game_detail", team_id=team.id, game_id=game.id)
    )

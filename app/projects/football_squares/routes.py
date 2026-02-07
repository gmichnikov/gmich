from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app import db
from app.projects.football_squares import football_squares_bp
from app.projects.football_squares.models import FootballSquaresGrid, FootballSquaresParticipant, FootballSquaresSquare, FootballSquaresQuarter, AxisType
import uuid

@football_squares_bp.route("/")
@login_required
def index():
    grids = FootballSquaresGrid.query.filter_by(user_id=current_user.id).order_by(FootballSquaresGrid.created_at.desc()).all()
    return render_template("football_squares/list.html", grids=grids)

@football_squares_bp.route("/create", methods=["GET", "POST"])
@login_required
def create():
    if request.method == "POST":
        name = request.form.get("name")
        team1_name = request.form.get("team1_name")
        team1_color_primary = request.form.get("team1_color_primary", "#000000")
        team1_color_secondary = request.form.get("team1_color_secondary", "#FFFFFF")
        team2_name = request.form.get("team2_name")
        team2_color_primary = request.form.get("team2_color_primary", "#000000")
        team2_color_secondary = request.form.get("team2_color_secondary", "#FFFFFF")
        axis_type = request.form.get("axis_type", "Draft")
        
        if not name or not team1_name or not team2_name:
            flash("Please fill in all required fields.")
            return render_template("football_squares/create_edit.html", mode="create")
        
        grid = FootballSquaresGrid(
            user_id=current_user.id,
            name=name,
            share_slug=str(uuid.uuid4()),
            team1_name=team1_name,
            team1_color_primary=team1_color_primary,
            team1_color_secondary=team1_color_secondary,
            team2_name=team2_name,
            team2_color_primary=team2_color_primary,
            team2_color_secondary=team2_color_secondary,
            axis_type=AxisType[axis_type]
        )
        
        db.session.add(grid)
        db.session.commit()
        
        flash(f"Grid '{name}' created successfully!")
        return redirect(url_for("football_squares.dashboard", grid_id=grid.id))
        
    return render_template("football_squares/create_edit.html", mode="create")

@football_squares_bp.route("/<int:grid_id>")
@login_required
def dashboard(grid_id):
    grid = FootballSquaresGrid.query.get_or_404(grid_id)
    if grid.user_id != current_user.id:
        abort(404)
    return render_template("football_squares/dashboard.html", grid=grid)

@football_squares_bp.route("/<int:grid_id>/edit", methods=["GET", "POST"])
@login_required
def edit(grid_id):
    grid = FootballSquaresGrid.query.get_or_404(grid_id)
    if grid.user_id != current_user.id:
        abort(404)
        
    if request.method == "POST":
        grid.name = request.form.get("name")
        grid.team1_name = request.form.get("team1_name")
        grid.team1_color_primary = request.form.get("team1_color_primary")
        grid.team1_color_secondary = request.form.get("team1_color_secondary")
        grid.team2_name = request.form.get("team2_name")
        grid.team2_color_primary = request.form.get("team2_color_primary")
        grid.team2_color_secondary = request.form.get("team2_color_secondary")
        
        db.session.commit()
        flash("Grid updated successfully!")
        return redirect(url_for("football_squares.dashboard", grid_id=grid.id))
        
    return render_template("football_squares/create_edit.html", mode="edit", grid=grid)

@football_squares_bp.route("/<int:grid_id>/delete", methods=["POST"])
@login_required
def delete(grid_id):
    grid = FootballSquaresGrid.query.get_or_404(grid_id)
    if grid.user_id != current_user.id:
        abort(404)
        
    db.session.delete(grid)
    db.session.commit()
    flash("Grid deleted successfully!")
    return redirect(url_for("football_squares.index"))

@football_squares_bp.route("/view/<string:share_slug>")
def public_view(share_slug):
    grid = FootballSquaresGrid.query.filter_by(share_slug=share_slug).first_or_404()
    return render_template("football_squares/public_view.html", grid=grid)

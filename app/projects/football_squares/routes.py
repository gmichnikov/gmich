from flask import render_template, redirect, url_for, flash, request, abort, jsonify
from flask_login import login_required, current_user
from app import db
from app.projects.football_squares import football_squares_bp
from app.projects.football_squares.models import FootballSquaresGrid, FootballSquaresParticipant, FootballSquaresSquare, FootballSquaresQuarter, AxisType
import uuid
import random

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
        axis_type_str = request.form.get("axis_type", "Draft")
        
        if not name or not team1_name or not team2_name:
            flash("Please fill in all required fields.")
            return render_template("football_squares/create_edit.html", mode="create")
        
        axis_type = AxisType[axis_type_str]
        team1_digits = "0,1,2,3,4,5,6,7,8,9"
        team2_digits = "0,1,2,3,4,5,6,7,8,9"
        
        if axis_type == AxisType.Random:
            d1 = list(range(10))
            d2 = list(range(10))
            random.shuffle(d1)
            random.shuffle(d2)
            team1_digits = ",".join(map(str, d1))
            team2_digits = ",".join(map(str, d2))

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
            axis_type=axis_type,
            team1_digits=team1_digits,
            team2_digits=team2_digits
        )
        
        db.session.add(grid)
        # Initialize 100 empty squares
        for x in range(10):
            for y in range(10):
                square = FootballSquaresSquare(grid=grid, x_coord=x, y_coord=y)
                db.session.add(square)
        
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
    
    # Ensure squares are initialized (for grids created before initialization was added)
    if len(grid.squares) == 0:
        for x in range(10):
            for y in range(10):
                square = FootballSquaresSquare(grid_id=grid.id, x_coord=x, y_coord=y)
                db.session.add(square)
        db.session.commit()
        # Refresh grid object
        grid = FootballSquaresGrid.query.get(grid_id)

    total_assigned_squares = sum(p.square_count for p in grid.participants)
    is_locked = any(s.participant_id is not None for s in grid.squares)
    
    # Create a mapping of squares for easier lookup in template
    squares_map = {(s.x_coord, s.y_coord): s for s in grid.squares}
    
    return render_template("football_squares/dashboard.html", 
                         grid=grid, 
                         total_assigned_squares=total_assigned_squares,
                         is_locked=is_locked,
                         squares_map=squares_map)

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

@football_squares_bp.route("/<int:grid_id>/participants/add", methods=["POST"])
@login_required
def add_participant(grid_id):
    grid = FootballSquaresGrid.query.get_or_404(grid_id)
    if grid.user_id != current_user.id:
        abort(404)
    
    # Check if locked
    if any(s.participant_id is not None for s in grid.squares):
        flash("Cannot add participants after squares have been assigned.")
        return redirect(url_for("football_squares.dashboard", grid_id=grid.id))
        
    name = request.form.get("name")
    square_count = int(request.form.get("square_count", 0))
    
    if name:
        participant = FootballSquaresParticipant(grid_id=grid.id, name=name, square_count=square_count)
        db.session.add(participant)
        db.session.commit()
        flash(f"Added participant {name}.")
    
    return redirect(url_for("football_squares.dashboard", grid_id=grid.id))

@football_squares_bp.route("/participants/<int:participant_id>/update", methods=["POST"])
@login_required
def update_participant(participant_id):
    participant = FootballSquaresParticipant.query.get_or_404(participant_id)
    grid = participant.grid
    if grid.user_id != current_user.id:
        abort(404)
        
    square_count = int(request.form.get("square_count", 0))
    participant.square_count = square_count
    db.session.commit()
    
    return redirect(url_for("football_squares.dashboard", grid_id=grid.id))

@football_squares_bp.route("/participants/<int:participant_id>/delete", methods=["POST"])
@login_required
def delete_participant(participant_id):
    participant = FootballSquaresParticipant.query.get_or_404(participant_id)
    grid = participant.grid
    if grid.user_id != current_user.id:
        abort(404)
        
    # Check if locked
    if any(s.participant_id is not None for s in grid.squares):
        flash("Cannot remove participants after squares have been assigned.")
        return redirect(url_for("football_squares.dashboard", grid_id=grid.id))
        
    db.session.delete(participant)
    db.session.commit()
    flash("Participant removed.")
    
    return redirect(url_for("football_squares.dashboard", grid_id=grid.id))

@football_squares_bp.route("/<int:grid_id>/axis/toggle", methods=["POST"])
@login_required
def toggle_axis(grid_id):
    grid = FootballSquaresGrid.query.get_or_404(grid_id)
    if grid.user_id != current_user.id:
        abort(404)
        
    if grid.axis_type == AxisType.Draft:
        grid.axis_type = AxisType.Random
        # Shuffle when switching to random
        d1 = list(range(10))
        d2 = list(range(10))
        random.shuffle(d1)
        random.shuffle(d2)
        grid.team1_digits = ",".join(map(str, d1))
        grid.team2_digits = ",".join(map(str, d2))
    else:
        grid.axis_type = AxisType.Draft
        grid.team1_digits = "0,1,2,3,4,5,6,7,8,9"
        grid.team2_digits = "0,1,2,3,4,5,6,7,8,9"
        
    db.session.commit()
    return redirect(url_for("football_squares.dashboard", grid_id=grid.id))

@football_squares_bp.route("/<int:grid_id>/axis/shuffle", methods=["POST"])
@login_required
def shuffle_axis(grid_id):
    grid = FootballSquaresGrid.query.get_or_404(grid_id)
    if grid.user_id != current_user.id:
        abort(404)
        
    if grid.axis_type == AxisType.Random:
        d1 = list(range(10))
        d2 = list(range(10))
        random.shuffle(d1)
        random.shuffle(d2)
        grid.team1_digits = ",".join(map(str, d1))
        grid.team2_digits = ",".join(map(str, d2))
        db.session.commit()
        flash("Axes re-shuffled.")
    
    return redirect(url_for("football_squares.dashboard", grid_id=grid.id))

@football_squares_bp.route("/<int:grid_id>/squares/assign", methods=["POST"])
@login_required
def assign_square(grid_id):
    grid = FootballSquaresGrid.query.get_or_404(grid_id)
    if grid.user_id != current_user.id:
        abort(404)
        
    data = request.get_json()
    x = data.get("x")
    y = data.get("y")
    participant_id = data.get("participant_id") # Can be null to unassign
    
    square = FootballSquaresSquare.query.filter_by(grid_id=grid.id, x_coord=x, y_coord=y).first()
    if not square:
        return jsonify({"success": False, "error": "Square not found"}), 404
        
    if participant_id:
        # Check if participant belongs to this grid
        participant = FootballSquaresParticipant.query.get(participant_id)
        if not participant or participant.grid_id != grid.id:
            return jsonify({"success": False, "error": "Invalid participant"}), 400
        square.participant_id = participant_id
    else:
        square.participant_id = None
        
    db.session.commit()
    return jsonify({"success": True})

@football_squares_bp.route("/<int:grid_id>/randomize/all", methods=["POST"])
@login_required
def randomize_all(grid_id):
    grid = FootballSquaresGrid.query.get_or_404(grid_id)
    if grid.user_id != current_user.id:
        abort(404)
        
    # Clear all assignments
    for square in grid.squares:
        square.participant_id = None
        
    # Get participants and their target counts
    participants = grid.participants
    pool = []
    for p in participants:
        pool.extend([p.id] * p.square_count)
    
    # Trim or pad pool to 100 if necessary (though user should ideally set it to 100)
    pool = pool[:100]
    random.shuffle(pool)
    
    # Assign to squares
    squares = list(grid.squares)
    random.shuffle(squares)
    
    for i, p_id in enumerate(pool):
        if i < len(squares):
            squares[i].participant_id = p_id
            
    db.session.commit()
    flash("Grid randomized successfully.")
    return redirect(url_for("football_squares.dashboard", grid_id=grid.id))

@football_squares_bp.route("/<int:grid_id>/randomize/remaining", methods=["POST"])
@login_required
def randomize_remaining(grid_id):
    grid = FootballSquaresGrid.query.get_or_404(grid_id)
    if grid.user_id != current_user.id:
        abort(404)
        
    # Calculate how many squares each participant already has
    participant_counts = {}
    for p in grid.participants:
        current_count = FootballSquaresSquare.query.filter_by(grid_id=grid.id, participant_id=p.id).count()
        remaining = max(0, p.square_count - current_count)
        participant_counts[p.id] = remaining
        
    # Create a pool of remaining assignments
    pool = []
    for p_id, count in participant_counts.items():
        pool.extend([p_id] * count)
        
    random.shuffle(pool)
    
    # Get empty squares
    empty_squares = [s for s in grid.squares if s.participant_id is None]
    random.shuffle(empty_squares)
    
    # Assign
    for i, p_id in enumerate(pool):
        if i < len(empty_squares):
            empty_squares[i].participant_id = p_id
            
    db.session.commit()
    flash("Remaining squares randomized.")
    return redirect(url_for("football_squares.dashboard", grid_id=grid.id))

@football_squares_bp.route("/view/<string:share_slug>")
def public_view(share_slug):
    grid = FootballSquaresGrid.query.filter_by(share_slug=share_slug).first_or_404()
    return render_template("football_squares/public_view.html", grid=grid)

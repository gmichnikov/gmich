import secrets

from app.projects.bowling.models import BowlingGame


def generate_unique_game_code(max_attempts=100):
    """
    Return a random 6-digit zero-padded code not assigned to any existing game.
    Codes are never reused — each belongs to one game permanently.
    """
    for _ in range(max_attempts):
        code = f"{secrets.randbelow(1_000_000):06d}"
        if BowlingGame.query.filter_by(code=code).first() is None:
            return code
    raise RuntimeError("Unable to allocate a unique bowling game code")

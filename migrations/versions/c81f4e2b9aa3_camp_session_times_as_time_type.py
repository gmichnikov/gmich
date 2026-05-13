"""Camp session start/end as TIME instead of VARCHAR

Revision ID: c81f4e2b9aa3
Revises: 995406d8204f
Create Date: 2026-05-12

"""
from datetime import datetime

from alembic import op
import sqlalchemy as sa


revision = "c81f4e2b9aa3"
down_revision = "995406d8204f"
branch_labels = None
depends_on = None


def _parse_time_string(time_str):
    if not time_str:
        return None
    try:
        s = time_str.strip().upper()
        for fmt in ("%I:%M%p", "%I:%M %p", "%H:%M:%S", "%H:%M"):
            try:
                return datetime.strptime(s, fmt).time()
            except ValueError:
                continue
    except Exception:
        pass
    return None


def _fmt_clock_12h(t):
    if t is None:
        return None
    hour = t.hour
    minute = t.minute
    h12 = hour % 12 or 12
    suffix = "am" if hour < 12 else "pm"
    if minute:
        return f"{h12}:{minute:02d}{suffix}"
    return f"{h12}{suffix}"


def upgrade():
    op.add_column(
        "camps_session",
        sa.Column("start_time_new", sa.Time(), nullable=True),
    )
    op.add_column(
        "camps_session",
        sa.Column("end_time_new", sa.Time(), nullable=True),
    )

    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, start_time, end_time FROM camps_session")
    ).mappings().all()

    for row in rows:
        st = _parse_time_string(row["start_time"])
        et = _parse_time_string(row["end_time"])
        conn.execute(
            sa.text(
                "UPDATE camps_session SET start_time_new = :st, "
                "end_time_new = :et WHERE id = :id"
            ),
            {"st": st, "et": et, "id": row["id"]},
        )

    op.drop_column("camps_session", "start_time")
    op.drop_column("camps_session", "end_time")
    op.execute(
        "ALTER TABLE camps_session RENAME COLUMN start_time_new TO start_time"
    )
    op.execute(
        "ALTER TABLE camps_session RENAME COLUMN end_time_new TO end_time"
    )


def downgrade():
    op.add_column(
        "camps_session",
        sa.Column("start_time_str", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "camps_session",
        sa.Column("end_time_str", sa.String(length=50), nullable=True),
    )

    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, start_time, end_time FROM camps_session")
    ).mappings().all()

    for row in rows:
        conn.execute(
            sa.text(
                "UPDATE camps_session SET start_time_str = :st, "
                "end_time_str = :et WHERE id = :id"
            ),
            {"st": _fmt_clock_12h(row["start_time"]), "et": _fmt_clock_12h(row["end_time"]), "id": row["id"]},
        )

    op.drop_column("camps_session", "start_time")
    op.drop_column("camps_session", "end_time")
    op.execute(
        "ALTER TABLE camps_session RENAME COLUMN start_time_str TO start_time"
    )
    op.execute(
        "ALTER TABLE camps_session RENAME COLUMN end_time_str TO end_time"
    )

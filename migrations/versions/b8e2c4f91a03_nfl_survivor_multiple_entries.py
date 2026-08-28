"""Multiple entries per user: display_name on participants, picks by participant_id.

Revision ID: b8e2c4f91a03
Revises: a610197547dd
Create Date: 2026-08-28 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "b8e2c4f91a03"
down_revision = "a610197547dd"
branch_labels = None
depends_on = None


def upgrade():
    # Pool is being reset — no production entries to preserve.
    op.execute("DELETE FROM nfl_survivor_picks")
    op.execute("DELETE FROM nfl_survivor_participants")

    with op.batch_alter_table("nfl_survivor_participants", schema=None) as batch_op:
        batch_op.drop_constraint("uq_nfl_survivor_participant", type_="unique")
        batch_op.add_column(
            sa.Column("display_name", sa.String(length=100), nullable=False, server_default="Entry")
        )
        batch_op.create_unique_constraint(
            "uq_nfl_survivor_entry_name", ["season_id", "display_name"]
        )

    with op.batch_alter_table("nfl_survivor_participants", schema=None) as batch_op:
        batch_op.alter_column("display_name", server_default=None)

    with op.batch_alter_table("nfl_survivor_picks", schema=None) as batch_op:
        batch_op.drop_constraint("uq_nfl_survivor_pick", type_="unique")
        batch_op.drop_constraint("nfl_survivor_picks_user_id_fkey", type_="foreignkey")
        batch_op.drop_column("user_id")
        batch_op.add_column(sa.Column("participant_id", sa.Integer(), nullable=False))
        batch_op.create_foreign_key(
            "fk_nfl_survivor_picks_participant_id",
            "nfl_survivor_participants",
            ["participant_id"],
            ["id"],
        )
        batch_op.create_unique_constraint(
            "uq_nfl_survivor_pick", ["participant_id", "week"]
        )


def downgrade():
    op.execute("DELETE FROM nfl_survivor_picks")
    op.execute("DELETE FROM nfl_survivor_participants")

    with op.batch_alter_table("nfl_survivor_picks", schema=None) as batch_op:
        batch_op.drop_constraint("uq_nfl_survivor_pick", type_="unique")
        batch_op.drop_constraint("fk_nfl_survivor_picks_participant_id", type_="foreignkey")
        batch_op.drop_column("participant_id")
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=False))
        batch_op.create_foreign_key(
            "nfl_survivor_picks_user_id_fkey", "user", ["user_id"], ["id"]
        )
        batch_op.create_unique_constraint(
            "uq_nfl_survivor_pick", ["season_id", "user_id", "week"]
        )

    with op.batch_alter_table("nfl_survivor_participants", schema=None) as batch_op:
        batch_op.drop_constraint("uq_nfl_survivor_entry_name", type_="unique")
        batch_op.drop_column("display_name")
        batch_op.create_unique_constraint(
            "uq_nfl_survivor_participant", ["season_id", "user_id"]
        )

"""Fix family_member unique constraint to allow multiple family members

Revision ID: a1b2c3d4e5f6
Revises: d028c3445be6
Create Date: 2025-12-10 21:10:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "d028c3445be6"
branch_labels = None
depends_on = None


def upgrade():
    # Drop the existing unique constraint that prevents multiple family members
    # The constraint (user_id, is_self) prevents having multiple records with is_self=False
    # Use PostgreSQL's DROP CONSTRAINT IF EXISTS
    op.execute(
        text(
            """
        ALTER TABLE family_member 
        DROP CONSTRAINT IF EXISTS family_member_user_id_is_self_key
    """
        )
    )

    # For PostgreSQL, create a partial unique index that only applies when is_self=True
    # This ensures only one "self" record per user, but allows multiple non-self members
    op.execute(
        text(
            """
        CREATE UNIQUE INDEX IF NOT EXISTS family_member_user_id_is_self_unique 
        ON family_member (user_id) 
        WHERE is_self = true
    """
        )
    )


def downgrade():
    # Drop the partial unique index
    op.execute(text("DROP INDEX IF EXISTS family_member_user_id_is_self_unique"))

    # Restore the original unique constraint (though this will prevent multiple family members)
    # Note: This will fail if there are already multiple family members with is_self=False
    # In that case, the user will need to manually remove duplicates before downgrading
    op.create_unique_constraint(
        "family_member_user_id_is_self_key", "family_member", ["user_id", "is_self"]
    )

"""Update user credits to be non-nullable and set default for existing users

Revision ID: 91af2ce6a4c0
Revises: b0105b933f25
Create Date: 2024-06-05 17:55:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '91af2ce6a4c0'
down_revision = 'b0105b933f25'
branch_labels = None
depends_on = None


def upgrade():
    # First, update any NULL credits to 10
    op.execute("UPDATE \"user\" SET credits = 10 WHERE credits IS NULL")
    
    # Then make the column non-nullable
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.alter_column('credits',
               existing_type=sa.INTEGER(),
               nullable=False,
               existing_server_default=sa.text('10'))


def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.alter_column('credits',
               existing_type=sa.INTEGER(),
               nullable=True,
               existing_server_default=sa.text('10'))

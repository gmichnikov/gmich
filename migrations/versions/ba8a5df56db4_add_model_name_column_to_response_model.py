"""Add model_name column to Response model

Revision ID: ba8a5df56db4
Revises: c131a6273e60
Create Date: 2025-06-05 18:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ba8a5df56db4'
down_revision = 'c131a6273e60'
branch_labels = None
depends_on = None


def upgrade():
    # First add the column as nullable
    with op.batch_alter_table('response', schema=None) as batch_op:
        batch_op.add_column(sa.Column('model_name', sa.String(length=100), nullable=True))

    # Update existing records with default model names
    connection = op.get_bind()
    connection.execute(sa.text(
        """
        UPDATE response 
        SET model_name = CASE 
            WHEN llm_name = 'GPT-4.1-mini' THEN 'gpt-4.1-mini'
            WHEN llm_name = 'Claude' THEN 'claude-3-5-haiku-latest'
            WHEN llm_name = 'Gemini' THEN 'gemini-2.0-flash'
            ELSE llm_name
        END
        """
    ))

    # Now make the column non-nullable
    with op.batch_alter_table('response', schema=None) as batch_op:
        batch_op.alter_column('model_name',
                            existing_type=sa.String(length=100),
                            nullable=False)


def downgrade():
    with op.batch_alter_table('response', schema=None) as batch_op:
        batch_op.drop_column('model_name')

"""Remove district_ward column from disease_cases

Revision ID: remove_district_ward
Revises: 
Create Date: 2026-06-04

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'remove_district_ward'
down_revision = None  # Set this to your latest migration revision if you have one
branch_labels = None
depends_on = None


def upgrade():
    # Remove district_ward column from disease_cases table
    with op.batch_alter_table('disease_cases', schema=None) as batch_op:
        batch_op.drop_column('district_ward')


def downgrade():
    # Add district_ward column back if needed
    with op.batch_alter_table('disease_cases', schema=None) as batch_op:
        batch_op.add_column(sa.Column('district_ward', sa.String(length=100), nullable=True))
        batch_op.create_index('ix_disease_cases_district_ward', ['district_ward'], unique=False)

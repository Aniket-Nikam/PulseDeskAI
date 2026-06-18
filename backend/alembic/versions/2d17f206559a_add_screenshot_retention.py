"""add screenshot retention days to system settings

Revision ID: 2d17f206559a
Revises: 19b16f196448
Create Date: 2026-05-28 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2d17f206559a'
down_revision: Union[str, None] = '19b16f196448'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('system_settings', sa.Column('screenshot_retention_days', sa.Integer(), nullable=False, server_default='30'))


def downgrade() -> None:
    op.drop_column('system_settings', 'screenshot_retention_days')

"""add is_deleted to comments

Revision ID: 714bac7e172c
Revises: c9723583d324
Create Date: 2026-09-21 19:34:24.119397

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '714bac7e172c'
down_revision: Union[str, Sequence[str], None] = 'c9723583d324'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.add_column(
        'comments',
        sa.Column(
            'is_deleted',
            sa.Boolean(),
            server_default='0',
            nullable=False
        )
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_column(
        'comments',
        'is_deleted'
    )
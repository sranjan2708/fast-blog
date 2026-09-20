"""add indexes for post queries

Revision ID: c9723583d324
Revises: 67a5382c4fa8
Create Date: 2026-09-20 23:02:19.344710

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9723583d324'
down_revision: Union[str, Sequence[str], None] = '67a5382c4fa8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add indexes for frequently queried post fields."""

    op.create_index(
        'ix_posts_user_id',
        'posts',
        ['user_id'],
        unique=False
    )

    op.create_index(
        'ix_posts_status',
        'posts',
        ['status'],
        unique=False
    )

    op.create_index(
        'ix_posts_created_at',
        'posts',
        ['created_at'],
        unique=False
    )


def downgrade() -> None:
    """Remove post query indexes."""

    op.drop_index(
        'ix_posts_created_at',
        table_name='posts'
    )

    op.drop_index(
        'ix_posts_status',
        table_name='posts'
    )

    op.drop_index(
        'ix_posts_user_id',
        table_name='posts'
    )
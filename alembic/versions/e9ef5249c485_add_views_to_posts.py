"""add views to posts

Revision ID: e9ef5249c485
Revises: 714bac7e172c
Create Date: 2026-09-23 19:55:51.513305

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e9ef5249c485'
down_revision: Union[str, Sequence[str], None] = '714bac7e172c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'posts',
        sa.Column(
            'views',
            sa.Integer(),
            server_default='0',
            nullable=False
        )
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column(
        'posts',
        'views'
    )
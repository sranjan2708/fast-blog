"""add user preferences

Revision ID: b0d38b69f05a
Revises: 4f41d7145df6
Create Date: 2026-09-24 18:56:25.371409

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b0d38b69f05a'
down_revision: Union[str, Sequence[str], None] = '4f41d7145df6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # Add theme preference
    op.add_column(
        'users',
        sa.Column(
            'theme',
            sa.String(length=20),
            nullable=False,
            server_default='light'
        )
    )

    # Add posts per page preference
    op.add_column(
        'users',
        sa.Column(
            'posts_per_page',
            sa.Integer(),
            nullable=False,
            server_default='10'
        )
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_column(
        'users',
        'posts_per_page'
    )

    op.drop_column(
        'users',
        'theme'
    )
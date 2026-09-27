"""add created_at to comments

Revision ID: 6a5c8b671b05
Revises: b0d38b69f05a
Create Date: 2026-09-27 22:20:03.175282

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6a5c8b671b05'
down_revision: Union[str, Sequence[str], None] = 'b0d38b69f05a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # ------------------------------------------------------
    # Add created_at column temporarily as nullable
    # ------------------------------------------------------

    op.add_column(
        'comments',
        sa.Column(
            'created_at',
            sa.DateTime(),
            nullable=True
        )
    )

    # ------------------------------------------------------
    # Set a timestamp for existing comments
    # ------------------------------------------------------

    op.execute(
        """
        UPDATE comments
        SET created_at = CURRENT_TIMESTAMP
        WHERE created_at IS NULL
        """
    )

    # ------------------------------------------------------
    # Make created_at mandatory
    # ------------------------------------------------------

    op.alter_column(
        'comments',
        'created_at',
        existing_type=sa.DateTime(),
        nullable=False
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_column(
        'comments',
        'created_at'
    )
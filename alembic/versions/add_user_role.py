"""add role to users

Revision ID: add_user_role
Revises: 205d47804ad6
Create Date: 2026-09-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "add_user_role"
down_revision: Union[str, Sequence[str], None] = "205d47804ad6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users",
        sa.Column(
            "role",
            sa.String(length=20),
            nullable=False,
            server_default="user"
        )
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "role")
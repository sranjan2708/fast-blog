"""create post views

Revision ID: fc44d53c896c
Revises: e9ef5249c485
Create Date: 2026-09-23 20:11:54.651823

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fc44d53c896c'
down_revision: Union[str, Sequence[str], None] = 'e9ef5249c485'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'post_views',
        sa.Column(
            'id',
            sa.Integer(),
            nullable=False
        ),
        sa.Column(
            'user_id',
            sa.Integer(),
            nullable=False
        ),
        sa.Column(
            'post_id',
            sa.Integer(),
            nullable=False
        ),
        sa.Column(
            'viewed_at',
            sa.DateTime(),
            nullable=False
        ),
        sa.ForeignKeyConstraint(
            ['post_id'],
            ['posts.id']
        ),
        sa.ForeignKeyConstraint(
            ['user_id'],
            ['users.id']
        ),
        sa.PrimaryKeyConstraint(
            'id'
        ),
        sa.UniqueConstraint(
            'user_id',
            'post_id',
            name='uq_user_post_view'
        )
    )

    op.create_index(
        op.f('ix_post_views_id'),
        'post_views',
        ['id'],
        unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f('ix_post_views_id'),
        table_name='post_views'
    )

    op.drop_table(
        'post_views'
    )
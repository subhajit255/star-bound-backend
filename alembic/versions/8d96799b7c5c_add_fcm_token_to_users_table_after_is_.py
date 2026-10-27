"""add fcm_token to users table after is_active

Revision ID: 8d96799b7c5c
Revises: 299dbb9ad4a5
Create Date: 2026-10-26 22:02:53.874661

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8d96799b7c5c'
down_revision: Union[str, Sequence[str], None] = '299dbb9ad4a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TABLE users ADD COLUMN fcm_token VARCHAR(512) NULL COMMENT 'Firebase Cloud Messaging device token' AFTER is_active")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'fcm_token')

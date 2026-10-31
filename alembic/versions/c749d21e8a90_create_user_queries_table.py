"""create user_queries table

Revision ID: c749d21e8a90
Revises: ab13f1903521
Create Date: 2026-10-31 23:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = 'c749d21e8a90'
down_revision: Union[str, Sequence[str], None] = 'ab13f1903521'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'user_queries',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('subject', sa.String(length=255), nullable=True, comment='query subject'),
        sa.Column('message', mysql.LONGTEXT(), nullable=True, comment='query message'),
        sa.Column('file', sa.String(length=255), nullable=True, comment='query file'),
        sa.Column('reply', mysql.LONGTEXT(), nullable=True, comment='reply message'),
        sa.Column('replied_by', sa.BigInteger(), nullable=True),
        sa.Column('replied_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.Integer(), nullable=True, server_default='0', comment='query status 0-pending, 1-replied, 2-closed'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['replied_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_queries_id'), 'user_queries', ['id'], unique=False)
    op.create_index(op.f('ix_user_queries_user_id'), 'user_queries', ['user_id'], unique=False)
    op.create_index(op.f('ix_user_queries_replied_by'), 'user_queries', ['replied_by'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_user_queries_replied_by'), table_name='user_queries')
    op.drop_index(op.f('ix_user_queries_user_id'), table_name='user_queries')
    op.drop_index(op.f('ix_user_queries_id'), table_name='user_queries')
    op.drop_table('user_queries')


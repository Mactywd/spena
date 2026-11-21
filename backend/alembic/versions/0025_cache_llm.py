"""i token letti e scritti in cache in llm_calls, per rifare ogni costo dalla sua riga

Revision ID: 0025
"""
import sqlalchemy as sa
from alembic import op

revision = "0025"
down_revision = "0024"


def upgrade() -> None:
    op.add_column("llm_calls", sa.Column("cache_read_tokens", sa.Integer(), nullable=True))
    op.add_column("llm_calls", sa.Column("cache_write_tokens", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("llm_calls", "cache_write_tokens")
    op.drop_column("llm_calls", "cache_read_tokens")

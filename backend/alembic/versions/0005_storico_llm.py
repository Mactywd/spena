"""storico delle chiamate all'LLM: quanto è costata ogni sezione

Revision ID: 0005
"""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"


def upgrade() -> None:
    op.create_table(
        "llm_calls",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("call_site", sa.String(40), nullable=False),
        sa.Column("ok", sa.Boolean(), nullable=False),
        # annullabili perché possono davvero mancare: `cost` è nullable per
        # OpenRouter stessa, e una richiesta rifiutata non porta `usage` affatto
        sa.Column("model", sa.String(120), nullable=True),
        sa.Column("generation_id", sa.String(120), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_llm_calls_created_at_call_site", "llm_calls", ["created_at", "call_site"]
    )


def downgrade() -> None:
    op.drop_index("ix_llm_calls_created_at_call_site", table_name="llm_calls")
    op.drop_table("llm_calls")

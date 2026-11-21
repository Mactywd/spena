"""le modifiche della ricetta ricordano gli ingredienti che hanno creato

Revision ID: 0023
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0023"
down_revision = "0022"


def upgrade() -> None:
    op.add_column(
        "recipe_changes",
        sa.Column(
            "created_ingredient_ids",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("recipe_changes", "created_ingredient_ids")

"""una riga di lista della scheda ricorda le righe di dispensa che l'hanno portata

Revision ID: 0026
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0026"
down_revision = "0025"


def upgrade() -> None:
    # Le righe scritte prima valgono `[]`: stanno in piedi da sole, come finora.
    op.add_column(
        "change_card_rows",
        sa.Column(
            "from_pantry_row_ids",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("change_card_rows", "from_pantry_row_ids")

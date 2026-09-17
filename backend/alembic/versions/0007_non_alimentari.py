"""se una voce dell'anagrafica è cibo o no

Revision ID: 0007
"""
import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"


def upgrade() -> None:
    # server_default per riempire le righe che ci sono — in produzione al
    # 2026-09-17 sono 204, le 169 del seme più quelle create dalle decisioni
    # dell'import, tutte in reparti alimentari — e poi tolto subito: l'unico
    # scrittore deve tornare a essere create_ingredient, e una riga senza kind
    # deve fallire invece di diventare cibo in silenzio.
    op.add_column(
        "ingredients",
        sa.Column("kind", sa.String(length=10), nullable=False, server_default="food"),
    )
    op.alter_column("ingredients", "kind", server_default=None)


def downgrade() -> None:
    op.drop_column("ingredients", "kind")

"""il termine sa se ha creato il suo ingrediente

Revision ID: 0011
"""
import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"


def upgrade() -> None:
    # Nessun passo dati: per le decisioni già prese il fatto non è mai stato scritto, e
    # non si ricava (vedi `_decided_action` in `app/api/imports.py`). NULL vuol dire
    # «non si sa», e l'annullamento non cancella niente su un NULL.
    op.add_column(
        "import_terms", sa.Column("created_ingredient", sa.Boolean(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("import_terms", "created_ingredient")

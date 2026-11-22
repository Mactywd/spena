"""la variante di una ricetta ricorda da quale nasce (R8)

Revision ID: 0014
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0014"
down_revision = "0013"


def upgrade() -> None:
    # Annullabile e senza passo dati: ogni ricetta di oggi non è una variante, e non lo
    # diventa. `SET NULL` e non `CASCADE`: cancellare l'originale — lo fa solo
    # l'annullamento di una decisione dell'import, che la rifà subito dopo, o
    # `drop_seed_recipes` — non deve buttare il lavoro di chi ha scritto la variante. E
    # non `RESTRICT`, che quell'annullamento lo bloccherebbe. Nessun indice: si legge per
    # chiave primaria dell'originale, e le varianti di una ricetta le cerca solo
    # l'annullamento, raro e a mano.
    op.add_column(
        "recipes", sa.Column("derived_from_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_foreign_key(
        "recipes_derived_from_id_fkey", "recipes", "recipes",
        ["derived_from_id"], ["id"], ondelete="SET NULL",
    )


def downgrade() -> None:
    # Scendere perde i legami: le varianti restano, come ricette qualunque.
    op.drop_constraint("recipes_derived_from_id_fkey", "recipes", type_="foreignkey")
    op.drop_column("recipes", "derived_from_id")

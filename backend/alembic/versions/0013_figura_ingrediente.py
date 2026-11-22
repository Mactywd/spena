"""la figura dell'ingrediente in dispensa (S12)

Revision ID: 0013
"""
import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"


def upgrade() -> None:
    # Nessun passo dati: ogni ingrediente resta `NULL`, «non deciso», e mostra l'icona del
    # reparto finché `python -m app.cli.decide_emoji` non lo decide. È un comando a parte
    # e non un passo qui perché chiama l'AI: una migrazione che va in rete renderebbe
    # l'avvio del backend (che migra da sé, `docker-entrypoint.sh`) dipendente da
    # OpenRouter. I tre stati della colonna sono spiegati in `app/domain/emoji.py`.
    op.add_column("ingredients", sa.Column("emoji", sa.String(16), nullable=True))


def downgrade() -> None:
    # Scendere perde le figure decise, dall'AI e a mano.
    op.drop_column("ingredients", "emoji")

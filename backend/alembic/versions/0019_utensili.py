"""gli utensili di cucina (spec 2026-11-12 §4.4)

Revision ID: 0019
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0019"
# La testa di `master` quando la catena dei pasti è stata scritta: al merge questa riga
# va ripuntata sulla testa di `master` di quel momento, e `alembic heads` deve tornare
# una riga sola.
down_revision = "0018"


def upgrade() -> None:
    # Gli strumenti che Mattia ha in cucina. Nessun legame con le righe delle ricette né
    # con gli ingredienti (spec §4.4); il nome non è unico, per scelta (decisione 5).
    op.create_table(
        "utensils",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("note", sa.String(200), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("btrim(name) <> ''", name="ck_utensils_name_not_blank"),
    )


def downgrade() -> None:
    op.drop_table("utensils")

"""i nutrienti dell'ingrediente generico da CIQUAL 2025 (S4, fetta 1)

Revision ID: 0016

`down_revision` è la `0012`, la testa di `master` quando il piano è stato scritto: altri
piani della stessa notte aggiungono la `0013`, la `0014`, la `0015` e la `0018`. Al merge
va ripuntata sulla testa di `master` di quel momento (una riga), e `alembic heads` deve
dire una testa sola (piano `2026-10-13-s4-ciqual.md`, «Al merge»).
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0016"
down_revision = "0012"


def upgrade() -> None:
    # Nessun passo dati: la tabella si riempie con `python -m app.cli.load_ciqual` e le
    # scelte con `python -m app.cli.decide_ciqual`, a mano. Un passo qui renderebbe
    # l'avvio del backend (che migra da sé) dipendente da un file e da OpenRouter.
    op.create_table(
        "ciqual_foods",
        sa.Column("code", sa.String(10), primary_key=True),
        sa.Column("name_fr", sa.String(300), nullable=False),
        sa.Column("group_fr", sa.String(200), nullable=True),
        sa.Column("nutrients", postgresql.JSONB(), nullable=False),
        sa.Column("version", sa.String(10), nullable=False),
    )
    op.create_table(
        "ingredient_nutrition",
        sa.Column(
            "ingredient_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ingredients.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "ciqual_code",
            sa.String(10),
            sa.ForeignKey("ciqual_foods.code", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("decided_by", sa.String(20), nullable=False),
        sa.Column(
            "decided_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "decided_by IN ('ai', 'human')", name="ck_ingredient_nutrition_decided_by"
        ),
    )


def downgrade() -> None:
    # Scendere perde la tabella caricata e ogni scelta, dell'AI e a mano.
    op.drop_table("ingredient_nutrition")
    op.drop_table("ciqual_foods")

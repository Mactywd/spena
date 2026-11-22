"""i sostituti degli ingredienti (R5)

Revision ID: 0015
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0015"
# Numero riservato dalla fase giorno del 2026-10-13: R5 parte da `master`, ferma alla
# `0012`. Al merge del rilascio 2026-10-19 ripuntata sulla `0014` (R8), e
# `alembic heads` deve dire una testa sola (il piano, «Al merge»).
down_revision = "0014"


def upgrade() -> None:
    # Nessun passo dati: le risposte le scrive `python -m app.cli.decide_substitutes`, o
    # «Sostituisci» la prima volta che serve. Un comando a parte e non un passo qui perché
    # chiama l'AI: una migrazione che va in rete renderebbe l'avvio del backend (che migra
    # da sé, `docker-entrypoint.sh`) dipendente da OpenRouter.
    op.create_table(
        "ingredient_substitutions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ingredient_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("context", sa.String(10)),
        sa.Column("recipe_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("recipes.id", ondelete="CASCADE")),
        sa.Column("verdict", sa.String(20), nullable=False),
        sa.Column("decided_by", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.CheckConstraint("verdict IN ('substitutes', 'omit', 'irreplaceable')",
                           name="ck_substitution_verdict"),
        sa.CheckConstraint("decided_by IN ('ai', 'human')", name="ck_substitution_decided_by"),
        sa.CheckConstraint("context IS NULL OR context IN ('dolce', 'salato')",
                           name="ck_substitution_context"),
        sa.CheckConstraint("(recipe_id IS NULL) <> (context IS NULL)",
                           name="ck_substitution_scope"),
        sa.CheckConstraint("recipe_id IS NULL OR decided_by = 'human'",
                           name="ck_substitution_recipe_is_human"),
    )
    op.create_index(
        "uq_substitution_general", "ingredient_substitutions", ["ingredient_id", "context"],
        unique=True, postgresql_where=sa.text("recipe_id IS NULL"),
    )
    op.create_index(
        "uq_substitution_recipe", "ingredient_substitutions", ["recipe_id", "ingredient_id"],
        unique=True, postgresql_where=sa.text("recipe_id IS NOT NULL"),
    )
    op.create_table(
        "substitution_options",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("substitution_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("ingredient_substitutions.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("substitute_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("note", sa.String(60)),
        sa.Column("position", sa.SmallInteger, nullable=False),
        sa.UniqueConstraint("substitution_id", "substitute_id"),
    )
    op.create_index(
        "ix_substitution_options_substitute", "substitution_options", ["substitute_id"]
    )


def downgrade() -> None:
    # Scendere perde ogni risposta, dell'AI e scritta a mano.
    op.drop_table("substitution_options")
    op.drop_table("ingredient_substitutions")

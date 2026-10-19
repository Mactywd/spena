"""i grammi per ingrediente × unità canonica (S4, fetta 2)

Revision ID: 0017
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0017"
down_revision = "0016"


def upgrade() -> None:
    # Nessun passo dati: i pesi li decide `python -m app.cli.decide_grams`, a mano, perché
    # chiama l'AI. `NULLS NOT DISTINCT` vuole Postgres 15 o più (il progetto ha il 16).
    op.create_table(
        "ingredient_unit_grams",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "ingredient_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ingredients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "unit_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("units.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("grams", sa.Numeric(8, 2), nullable=True),
        sa.Column("decided_by", sa.String(20), nullable=False),
        sa.Column(
            "decided_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "ingredient_id",
            "unit_id",
            name="uq_ingredient_unit_grams",
            postgresql_nulls_not_distinct=True,
        ),
        sa.CheckConstraint("grams IS NULL OR grams > 0", name="ck_ingredient_unit_grams_positive"),
        sa.CheckConstraint(
            "decided_by IN ('ai', 'human')", name="ck_ingredient_unit_grams_decided_by"
        ),
    )


def downgrade() -> None:
    # Scendere perde ogni peso, dell'AI e a mano.
    op.drop_table("ingredient_unit_grams")

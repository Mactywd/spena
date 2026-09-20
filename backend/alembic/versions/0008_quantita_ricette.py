"""le quantità strutturate nelle ricette

Revision ID: 0008
"""
import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"


def upgrade() -> None:
    op.create_table(
        "units",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("key", sa.String(length=30), nullable=False, unique=True),
        sa.Column("singular", sa.String(length=30), nullable=True),
        sa.Column("plural", sa.String(length=30), nullable=True),
        sa.Column("decided_by", sa.String(length=20), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "canonical_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("units.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
            nullable=False,
        ),
    )
    # Nessun riempimento qui: lo fa `python -m app.cli.reparse_quantities`, perché il
    # parser migliorerà e migliorarlo non deve voler dire scrivere un'altra
    # migrazione. Stessa ragione per cui esiste `app.cli.reindex`.
    op.add_column(
        "recipe_ingredients", sa.Column("quantity_value", sa.Numeric(8, 3), nullable=True)
    )
    op.add_column(
        "recipe_ingredients",
        sa.Column(
            "quantity_unit_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("units.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "ck_recipe_ingredient_unit_needs_value",
        "recipe_ingredients",
        "quantity_unit_id IS NULL OR quantity_value IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_recipe_ingredient_unit_needs_value", "recipe_ingredients", type_="check"
    )
    op.drop_column("recipe_ingredients", "quantity_unit_id")
    op.drop_column("recipe_ingredients", "quantity_value")
    op.drop_table("units")

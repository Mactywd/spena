"""dispensa e lista della spesa

Revision ID: 0002
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"


def upgrade() -> None:
    op.create_table(
        "pantry_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ingredient_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("ingredients.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("products.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("note", sa.String(300)),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("status_changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('available', 'low', 'finished')", name="ck_pantry_status"),
    )
    # le query di disponibilità filtrano sempre le voci attive
    op.execute(
        "CREATE INDEX ix_pantry_active ON pantry_items (ingredient_id) "
        "WHERE archived_at IS NULL AND status <> 'finished'"
    )

    op.create_table(
        "shopping_list_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("raw_text", sa.String(200), nullable=False),
        sa.Column("ingredient_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("ingredients.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("reason", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True)),
        sa.Column("done_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('pending', 'checked', 'done', 'archived')",
                           name="ck_shopping_status"),
        sa.CheckConstraint(
            "reason IN ('manual', 'finished_while_cooking', 'low_while_cooking')",
            name="ck_shopping_reason",
        ),
    )
    op.create_index("ix_shopping_status", "shopping_list_items", ["status"])
    # alimenta l'ordinamento per frequenza dell'autocomplete
    op.create_index("ix_shopping_ingredient", "shopping_list_items", ["ingredient_id"])


def downgrade() -> None:
    op.drop_table("shopping_list_items")
    op.drop_table("pantry_items")

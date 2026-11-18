"""i pasti e il segno «nel ricettario» sulle ricette (spec 2026-11-12 §4.1, §4.2)

Revision ID: 0020
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0020"
down_revision = "0019"


def upgrade() -> None:
    # Le ricette che ci sono restano nel ricettario: il server_default le segna `true`.
    op.add_column(
        "recipes",
        sa.Column("in_book", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.create_table(
        "meals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("slot", sa.String(10), nullable=False),
        sa.Column("dish", sa.String(200), nullable=False),
        sa.Column("sides", sa.String(200), nullable=True),
        sa.Column("away", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("status", sa.String(10), server_default="official", nullable=False),
        sa.Column(
            "recipe_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("recipes.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "leftover_of_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("meals.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("day", "slot", name="uq_meals_day_slot"),
        sa.UniqueConstraint("recipe_id", name="uq_meals_recipe"),
        sa.CheckConstraint("slot IN ('lunch', 'dinner')", name="ck_meal_slot"),
        sa.CheckConstraint("status IN ('draft', 'official')", name="ck_meal_status"),
        sa.CheckConstraint("length(btrim(dish)) > 0", name="ck_meal_dish_not_blank"),
        sa.CheckConstraint(
            "leftover_of_id IS NULL OR recipe_id IS NULL", name="ck_meal_leftover_no_recipe"
        ),
        sa.CheckConstraint("NOT away OR recipe_id IS NULL", name="ck_meal_away_no_recipe"),
        sa.CheckConstraint(
            "NOT away OR leftover_of_id IS NULL", name="ck_meal_away_not_leftover"
        ),
        sa.CheckConstraint(
            "status = 'official' OR recipe_id IS NULL", name="ck_meal_draft_no_recipe"
        ),
        sa.CheckConstraint(
            "leftover_of_id IS NULL OR leftover_of_id <> id", name="ck_meal_not_own_leftover"
        ),
    )


def downgrade() -> None:
    op.drop_table("meals")
    op.drop_column("recipes", "in_book")

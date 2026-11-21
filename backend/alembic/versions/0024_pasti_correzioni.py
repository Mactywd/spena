"""un pasto fuori casa tiene la ricetta, una scheda può essere sostituita, un'inversa ricorda le origini

Revision ID: 0024
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0024"
down_revision = "0023"


def upgrade() -> None:
    op.drop_constraint("ck_meal_away_no_recipe", "meals", type_="check")
    op.drop_constraint("ck_card_status", "change_cards", type_="check")
    op.create_check_constraint(
        "ck_card_status",
        "change_cards",
        "status IN ('proposed', 'applied', 'discarded', 'superseded')",
    )
    op.add_column(
        "change_card_rows",
        sa.Column(
            "source_row_ids",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("change_card_rows", "source_row_ids")
    op.execute("UPDATE change_cards SET status = 'discarded' WHERE status = 'superseded'")
    op.drop_constraint("ck_card_status", "change_cards", type_="check")
    op.create_check_constraint(
        "ck_card_status", "change_cards", "status IN ('proposed', 'applied', 'discarded')"
    )
    # Le ricette fuori dal ricettario che il pasto fuori casa teneva da parte restano senza
    # pasto: si archiviano, perché una ricetta viva fuori dal ricettario ha sempre un pasto.
    op.execute(
        "UPDATE recipes SET archived_at = now() "
        "WHERE archived_at IS NULL AND NOT in_book "
        "AND id IN (SELECT recipe_id FROM meals WHERE away AND recipe_id IS NOT NULL)"
    )
    op.execute("UPDATE meals SET recipe_id = NULL WHERE away")
    op.create_check_constraint(
        "ck_meal_away_no_recipe", "meals", "NOT away OR recipe_id IS NULL"
    )

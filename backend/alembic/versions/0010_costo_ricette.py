"""il costo della ricetta

Revision ID: 0010
"""
import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"


def upgrade() -> None:
    # Nessun passo dati: le ricette importate lo prendono da `app.cli.reread_costs`,
    # che deve riscaricare le pagine, e le altre restano senza finché qualcuno lo
    # sceglie. Senza costo è la verità, non un difetto da riempire.
    op.add_column("recipes", sa.Column("cost", sa.SmallInteger(), nullable=True))
    op.create_check_constraint(
        "ck_recipe_cost", "recipes", "cost IS NULL OR cost BETWEEN 1 AND 5"
    )


def downgrade() -> None:
    op.drop_constraint("ck_recipe_cost", "recipes", type_="check")
    op.drop_column("recipes", "cost")

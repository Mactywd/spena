"""modificare ed eliminare una ricetta salvata (R10)

Revision ID: 0012
"""
import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"


def upgrade() -> None:
    # Presente vuol dire eliminata, come `pantry_items.archived_at`. Nessun indice: ogni
    # elenco di ricette filtra `IS NULL` su qualche migliaio di righe.
    op.add_column("recipes", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.drop_constraint("ck_recipe_import_state", "recipe_imports", type_="check")
    op.create_check_constraint(
        "ck_recipe_import_state",
        "recipe_imports",
        "state IN ('pending', 'imported', 'skipped', 'adopted')",
    )


def downgrade() -> None:
    # Scendere perde quel che R10 ha scritto, e va detto: una pagina presa in carico
    # torna `imported` (il vecchio CHECK non conosce altro), quindi l'import potrà di
    # nuovo rifare quella ricetta; e le ricette eliminate ricompaiono, perché la colonna
    # che le nascondeva se ne va.
    op.execute("UPDATE recipe_imports SET state = 'imported' WHERE state = 'adopted'")
    op.drop_constraint("ck_recipe_import_state", "recipe_imports", type_="check")
    op.create_check_constraint(
        "ck_recipe_import_state", "recipe_imports", "state IN ('pending', 'imported', 'skipped')"
    )
    op.drop_column("recipes", "archived_at")

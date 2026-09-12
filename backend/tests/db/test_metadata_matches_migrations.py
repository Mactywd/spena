"""Rete di sicurezza per `alembic revision --autogenerate`.

Le migrazioni sono scritte a mano: se i modelli e lo schema fisico divergono, il
primo autogenerate produce una migrazione dall'aspetto innocuo che cancella ciò
che i modelli non dichiarano. Questo test è ciò che impedisce la divergenza.
"""

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import text

import app.db.models  # noqa: F401  popola Base.metadata
from app.core.db import Base

MIGRATED_INDEXES = {
    "ix_aliases_alias_trgm",
    "ix_ingredients_name_trgm",
    "ix_pantry_active",
    "ix_products_ingredient_id",
    "ix_products_name_trgm",
    "ix_recipe_ingredients_ingredient",
    "ix_recipes_embedding",
    "ix_recipes_tsv",
    "ix_shopping_ingredient",
    "ix_shopping_status",
}


async def test_models_describe_the_migrated_schema(db_session):
    """Un autogenerate su questo database non deve proporre alcuna operazione."""
    connection = await db_session.connection()

    def _diff(sync_connection):
        context = MigrationContext.configure(sync_connection)
        return compare_metadata(context, Base.metadata)

    differences = await connection.run_sync(_diff)
    assert differences == [], f"l'autogenerate proporrebbe: {differences}"


async def test_every_migrated_index_is_declared_on_a_model(db_session):
    """I dieci indici esistono nel database e sono dichiarati nei modelli.

    `compare_metadata` da solo non basterebbe a dimostrarlo: un indice assente da
    entrambe le parti non produce differenze.
    """
    declared = {index.name for table in Base.metadata.tables.values() for index in table.indexes}
    assert MIGRATED_INDEXES <= declared

    rows = await db_session.execute(
        text("SELECT indexname FROM pg_indexes WHERE schemaname = current_schema()")
    )
    assert MIGRATED_INDEXES <= {row.indexname for row in rows}

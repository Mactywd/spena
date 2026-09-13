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
from app.db.models.pantry import PantryItem

MIGRATED_INDEXES = {
    "ix_aliases_alias_trgm",
    "ix_import_terms_queue",
    "ix_ingredients_name_trgm",
    "ix_pantry_active",
    "ix_products_ingredient_id",
    "ix_products_name_trgm",
    "ix_recipe_imports_state",
    "ix_recipe_ingredients_ingredient",
    "ix_recipes_category",
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
    """I tredici indici esistono nel database e sono dichiarati nei modelli.

    `compare_metadata` da solo non basterebbe a dimostrarlo: un indice assente da
    entrambe le parti non produce differenze.
    """
    declared = {index.name for table in Base.metadata.tables.values() for index in table.indexes}
    assert MIGRATED_INDEXES <= declared

    rows = await db_session.execute(
        text("SELECT indexname FROM pg_indexes WHERE schemaname = current_schema()")
    )
    assert MIGRATED_INDEXES <= {row.indexname for row in rows}


async def test_the_partial_index_predicate_is_more_than_a_name(db_session):
    """Alembic non confronta `postgresql_where`.

    Modello e database possono quindi divergere nel predicato senza che
    `compare_metadata` veda nulla, ed è il predicato a decidere quali voci della
    dispensa contano per la disponibilità: sbagliarlo fa sparire o ricomparire righe
    in silenzio. Confrontare le due stringhe a mano non funziona, perché Postgres
    riscrive la propria. Quindi si fa riscrivere anche quella del modello, creando un
    indice usa-e-getta con lo stesso predicato e rileggendo come il database lo
    normalizza. L'indice sparisce con il rollback del test.
    """
    declared = next(
        index for index in PantryItem.__table__.indexes if index.name == "ix_pantry_active"
    )
    predicate = declared.dialect_options["postgresql"]["where"]

    await db_session.execute(
        text(
            "CREATE INDEX ix_pantry_active_probe ON pantry_items (ingredient_id) "
            f"WHERE {predicate}"
        )
    )
    rows = await db_session.execute(
        text(
            "SELECT indexname, indexdef FROM pg_indexes "
            "WHERE indexname IN ('ix_pantry_active', 'ix_pantry_active_probe')"
        )
    )
    clauses = {name: definition.split(" WHERE ", 1)[1] for name, definition in rows}
    assert clauses["ix_pantry_active_probe"] == clauses["ix_pantry_active"]

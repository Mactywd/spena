import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.pantry import PantryItem
from app.db.models.product import Product
from app.db.models.shopping import ShoppingListItem, ShoppingReason, ShoppingStatus
from app.domain.rules import PantryStatus


async def _ingredient(db_session, name="pomodoro"):
    ingredient = Ingredient(name=name, display_name=name.capitalize(),
                            category=IngredientCategory.VERDURA)
    db_session.add(ingredient)
    await db_session.flush()
    return ingredient


async def test_pantry_item_works_without_a_product(db_session):
    """Le mele sfuse non hanno codice a barre né marca: devono entrare comunque."""
    ingredient = await _ingredient(db_session, "mela")
    item = PantryItem(ingredient_id=ingredient.id, status=PantryStatus.AVAILABLE)
    db_session.add(item)
    await db_session.flush()
    assert item.product_id is None
    assert item.archived_at is None


async def test_pantry_item_requires_an_ingredient(db_session):
    db_session.add(PantryItem(status=PantryStatus.AVAILABLE))
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_pantry_rejects_an_unknown_status(db_session):
    ingredient = await _ingredient(db_session)
    db_session.add(PantryItem(ingredient_id=ingredient.id, status="mezzo"))
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_two_products_of_the_same_ingredient_coexist(db_session):
    ingredient = await _ingredient(db_session, "yogurt greco")
    fage = Product(ingredient_id=ingredient.id, name="Fage Total 0%", source="openfoodfacts")
    carrefour = Product(ingredient_id=ingredient.id, name="Carrefour pesca", source="openfoodfacts")
    db_session.add_all([fage, carrefour])
    await db_session.flush()
    db_session.add_all([
        PantryItem(ingredient_id=ingredient.id, product_id=fage.id, status=PantryStatus.AVAILABLE),
        PantryItem(ingredient_id=ingredient.id, product_id=carrefour.id, status=PantryStatus.LOW),
    ])
    await db_session.flush()


async def test_shopping_item_survives_without_a_resolved_ingredient(db_session):
    """Mentre scrivi la lista non devi essere interrotto da una disambiguazione."""
    item = ShoppingListItem(raw_text="quella cosa verde del mercato",
                            status=ShoppingStatus.PENDING, reason=ShoppingReason.MANUAL)
    db_session.add(item)
    await db_session.flush()
    assert item.ingredient_id is None


async def test_shopping_rejects_an_unknown_status(db_session):
    db_session.add(ShoppingListItem(raw_text="x", status="comprato", reason=ShoppingReason.MANUAL))
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_shopping_rejects_an_unknown_reason(db_session):
    """Il vocabolario dei motivi è ciò che scrive il ciclo di cottura: va vincolato."""
    db_session.add(
        ShoppingListItem(raw_text="x", status=ShoppingStatus.PENDING, reason="perche-mi-va")
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_timestamp_columns_are_not_null_in_physical_schema(db_session):
    """I modelli dichiarano added_at/status_changed_at/created_at non opzionali:
    la migrazione deve rispecchiarlo con nullable=False, non solo l'ORM."""
    result = await db_session.execute(text(
        """
        SELECT table_name, column_name, is_nullable
        FROM information_schema.columns
        WHERE (table_name = 'pantry_items' AND column_name IN ('added_at', 'status_changed_at'))
           OR (table_name = 'shopping_list_items' AND column_name = 'created_at')
        """
    ))
    rows = {(row.table_name, row.column_name): row.is_nullable for row in result}
    assert rows == {
        ("pantry_items", "added_at"): "NO",
        ("pantry_items", "status_changed_at"): "NO",
        ("shopping_list_items", "created_at"): "NO",
    }

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.db.models.ingredient import Ingredient, IngredientAlias, IngredientCategory
from app.db.models.product import Product


async def test_ingredient_name_is_unique(db_session):
    db_session.add(Ingredient(name="pomodoro", display_name="Pomodoro",
                              category=IngredientCategory.VERDURA))
    await db_session.flush()
    db_session.add(Ingredient(name="pomodoro", display_name="Pomodoro Doppione",
                              category=IngredientCategory.VERDURA))
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_aliases_cascade_on_ingredient_delete(db_session):
    ingredient = Ingredient(name="yogurt greco", display_name="Yogurt greco",
                            category=IngredientCategory.LATTICINI)
    ingredient.aliases.append(IngredientAlias(alias="yoghurt greco", source="manual"))
    db_session.add(ingredient)
    await db_session.flush()

    await db_session.delete(ingredient)
    await db_session.flush()

    remaining = await db_session.execute(select(IngredientAlias))
    assert remaining.scalars().all() == []


async def test_barcode_is_unique_but_nullable(db_session):
    ingredient = Ingredient(name="yogurt greco", display_name="Yogurt greco",
                            category=IngredientCategory.LATTICINI)
    db_session.add(ingredient)
    await db_session.flush()

    # due prodotti senza codice a barre convivono: gli sfusi non ne hanno
    db_session.add(Product(ingredient_id=ingredient.id, name="Yogurt sfuso A", source="custom"))
    db_session.add(Product(ingredient_id=ingredient.id, name="Yogurt sfuso B", source="custom"))
    await db_session.flush()

    db_session.add(Product(ingredient_id=ingredient.id, name="Fage Total 0%",
                           brand="Fage", barcode="5201054000138", source="openfoodfacts"))
    await db_session.flush()
    db_session.add(Product(ingredient_id=ingredient.id, name="Doppione",
                           barcode="5201054000138", source="custom"))
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_product_requires_an_ingredient(db_session):
    db_session.add(Product(name="Orfano", source="custom"))
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_nutrients_roundtrip_as_json(db_session):
    ingredient = Ingredient(name="yogurt greco", display_name="Yogurt greco",
                            category=IngredientCategory.LATTICINI)
    db_session.add(ingredient)
    await db_session.flush()
    product = Product(
        ingredient_id=ingredient.id, name="Fage Total 0%", source="openfoodfacts",
        nutrients={"kcal": 57.0, "protein": 10.3, "carbs": 4.0, "fat": 0.0},
    )
    db_session.add(product)
    await db_session.flush()
    await db_session.refresh(product)
    assert product.nutrients["protein"] == 10.3


async def test_timestamp_columns_are_not_null_in_physical_schema(db_session):
    """TimestampMixin dichiara created_at/updated_at non opzionali: la migrazione
    deve rispecchiarlo con nullable=False, non solo l'ORM."""
    result = await db_session.execute(text(
        """
        SELECT table_name, column_name, is_nullable
        FROM information_schema.columns
        WHERE table_name IN ('ingredients', 'products')
          AND column_name IN ('created_at', 'updated_at')
        """
    ))
    rows = {(row.table_name, row.column_name): row.is_nullable for row in result}
    assert rows == {
        ("ingredients", "created_at"): "NO",
        ("ingredients", "updated_at"): "NO",
        ("products", "created_at"): "NO",
        ("products", "updated_at"): "NO",
    }


async def test_create_ingredient_deduce_il_kind_dal_reparto(db_session):
    """Il kind non è un parametro: chi crea sceglie il reparto e basta.

    Fallisce se qualcuno aggiunge un argomento `kind` alla firma, che è il modo
    in cui una riga «igiene ma è cibo» potrebbe nascere.
    """
    from app.domain.rules import IngredientKind
    from app.repositories.ingredients import create_ingredient

    cibo = await create_ingredient(db_session, "zucchina", "Zucchina", "verdura")
    non_cibo = await create_ingredient(db_session, "candeggina", "Candeggina", "casa")

    assert cibo.kind == IngredientKind.FOOD
    assert non_cibo.kind == IngredientKind.NON_FOOD


async def test_riassegnare_il_category_muove_il_kind(db_session):
    """Riassegnare la categoria di un ingrediente muove con sé il suo kind.

    La colonna `kind` è giustificata da questo comportamento: una riga creata in
    «verdura» che diventa «casa» deve diventare non-cibo, non rimanere cibo. Una
    derivazione che girasse solo in `create_ingredient` non terrebbe questo
    invariante al passo, e il test verifica che il modello lo mantiene.
    """
    from app.domain.rules import IngredientKind

    ingredient = Ingredient(
        name="pomodoro", display_name="Pomodoro",
        category=IngredientCategory.VERDURA
    )
    db_session.add(ingredient)
    await db_session.flush()

    # Appena creato in un reparto alimentare è cibo
    assert ingredient.kind == IngredientKind.FOOD

    # Riassegnare il reparto a uno non alimentare lo rende non-cibo
    ingredient.category = IngredientCategory.CASA
    await db_session.flush()
    assert ingredient.kind == IngredientKind.NON_FOOD

    # Verificare che il valore persiste nel database
    await db_session.refresh(ingredient)
    assert ingredient.kind == IngredientKind.NON_FOOD

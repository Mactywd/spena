import app.api.recipes
import app.services.recipe_writing


def test_resolve_lines_e_quello_che_usa_il_modulo():
    assert app.api.recipes.resolve_lines is app.services.recipe_writing.resolve_lines
    assert app.api.recipes.embedding_for is app.services.recipe_writing.embedding_for
    assert app.api.recipes.RepeatedIngredient is app.services.recipe_writing.RepeatedIngredient
    assert not hasattr(app.api.recipes, "_resolve_lines")
    assert not hasattr(app.api.recipes, "_RepeatedIngredient")
    assert not hasattr(app.api.recipes, "_embedding_for")

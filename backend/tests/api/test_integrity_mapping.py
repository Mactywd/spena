"""Le quattro rotte che scrivono non devono travestire un difetto nostro da conflitto.

Un `IntegrityError` su Postgres ha uno SQLSTATE che dice di che violazione si tratta, e
solo due di quei codici descrivono un gesto dell'utente: 23503 (riferimento pendente →
404) e 23505 (duplicato → 409). Tutto il resto — 23502 not-null, 23514 check constraint
— significa che il codice e lo schema hanno divergiuto, e rispondere «ingrediente
ripetuto nella ricetta» manda il proprietario a cercare un doppione che non c'è.

I rami 404 e 409 sono già difesi dai test delle rispettive rotte
(`test_creating_with_a_dangling_ingredient_is_404_not_500`,
`test_repeating_an_ingredient_in_a_recipe_is_409_not_500`,
`test_product_on_a_missing_ingredient_is_404_not_409`, `test_duplicate_barcode_is_still_409`,
`test_duplicate_ingredient_name_returns_409`, `test_alias_on_a_missing_ingredient_is_404_not_409`,
`test_duplicate_alias_is_still_409`). Qui si difende il terzo ramo, quello che non si
raggiunge da nessuna richiesta legittima: la violazione che non è né l'una né l'altra deve
risalire fino in cima e restare un 500 visibile.

Perché con un errore costruito a mano e non con una violazione vera: i vincoli che
produrrebbero 23502 e 23514 sono già sbarrati prima del database dagli enum e dai
`Field` di Pydantic (app/schemas/recipe.py, app/schemas/product.py). Il ramo esiste
proprio per il giorno in cui quella doppia difesa si sfalda, e per provarlo oggi l'unico
modo è iniettare l'errore che quel giorno arriverebbe.
"""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.db import is_missing_reference, is_unique_violation


class OrigConSqlstate(Exception):
    """Il driver sotto SQLAlchemy: `IntegrityError.orig`, che porta lo SQLSTATE."""

    def __init__(self, sqlstate: str) -> None:
        super().__init__(f"violazione {sqlstate}")
        self.sqlstate = sqlstate


def errore(sqlstate: str) -> IntegrityError:
    return IntegrityError("INSERT ...", None, OrigConSqlstate(sqlstate))


def test_i_due_predicati_distinguono_i_tre_casi():
    riferimento, duplicato, check = errore("23503"), errore("23505"), errore("23514")

    assert is_missing_reference(riferimento) and not is_unique_violation(riferimento)
    assert is_unique_violation(duplicato) and not is_missing_reference(duplicato)
    # il terzo caso non è né l'uno né l'altro: è ciò che fa scattare il `raise` nudo
    assert not is_missing_reference(check) and not is_unique_violation(check)


def test_un_orig_senza_sqlstate_non_e_nessuno_dei_due():
    """Un `IntegrityError` costruito altrove (o un driver diverso) non va indovinato."""
    senza = IntegrityError("INSERT ...", None, Exception("nessuno SQLSTATE"))
    assert not is_missing_reference(senza)
    assert not is_unique_violation(senza)


SITI = {
    "POST /recipes": (
        "app.api.recipes",
        "create_recipe",
        "/api/v1/recipes",
        {
            "title": "Ricetta", "instructions": "Nulla.", "source": "manual",
            "ingredients": [{"ingredient_id": str(uuid.uuid4()), "role": "primary"}],
        },
    ),
    "POST /ingredients": (
        "app.api.ingredients",
        "create_ingredient",
        "/api/v1/ingredients",
        {"name": "farro", "display_name": "Farro", "category": "cereali"},
    ),
    "POST /ingredients/{id}/aliases": (
        "app.api.ingredients",
        "add_alias",
        f"/api/v1/ingredients/{uuid.uuid4()}/aliases",
        {"alias": "farro decorticato"},
    ),
    "POST /products": (
        "app.api.products",
        "create_product",
        "/api/v1/products",
        {"ingredient_id": str(uuid.uuid4()), "name": "Farro Fage"},
    ),
}


@pytest.mark.parametrize("sito", sorted(SITI), ids=sorted(SITI))
async def test_una_violazione_che_non_e_ne_duplicato_ne_riferimento_resta_un_500(
    logged_client, monkeypatch, sito
):
    import importlib

    modulo_nome, funzione, url, corpo = SITI[sito]
    modulo = importlib.import_module(modulo_nome)

    async def esplode(*_args, **_kwargs):
        # 23514: un check constraint violato, cioè schema ed enum divergenti
        raise errore("23514")

    monkeypatch.setattr(modulo, funzione, esplode)

    # L'eccezione risale attraverso ASGITransport invece di diventare una risposta:
    # è esattamente ciò che in produzione è un 500 nei log, non un 409 all'utente.
    with pytest.raises(IntegrityError):
        await logged_client.post(url, json=corpo)

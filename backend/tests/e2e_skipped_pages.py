"""Semina, correzione e pulizia per `frontend/e2e/scartate.spec.ts`. Non è un test di pytest.

Le pagine scartate si provano nel browser vero solo se ce ne sono, e lo stack e2e non ne
ha: il seme porta anagrafica e ricette, non pagine dell'import, e nessuna rotta ne
scarica. Questo file le fa nascere **dal codice vero**: una pagina illeggibile con
`store_unparsable` — quel che fa lo scarico davanti a una pagina senza righe — e una
ricetta con una riga non alimentare scartata da `materialize_ready`, che scrive il
motivo come in produzione. `fix` corregge la causa col servizio vero dell'anagrafica,
`recategorize_ingredient`: la correzione che una persona fa dalla scheda
dell'ingrediente.

Si lancia dentro il container del backend, dove `./backend` è montato su `/app`:

    $E2E exec -T backend python tests/e2e_skipped_pages.py seed <etichetta>
    $E2E exec -T backend python tests/e2e_skipped_pages.py fix <id-ingrediente>
    $E2E exec -T backend python tests/e2e_skipped_pages.py clean

`seed` stampa su stdout, in JSON, quel che la prova cerca a video. `clean` toglie pagine,
ricette, termini e ingredienti di questo file, anche quelli di un giro interrotto: si può
rieseguire, e chiamare anche prima di seminare.

Scrive e cancella nel database, quindi **si rifiuta di partire fuori dallo stack e2e**:
vuole `SPENA_E2E=1`, che sta solo in `.env.e2e`.

Non si chiama `test_*.py` apposta: pytest non lo raccoglie.
"""

import os
import sys

if os.environ.get("SPENA_E2E") != "1":
    raise SystemExit(
        "e2e_skipped_pages.py scrive e cancella nel database: gira solo sullo stack "
        "spena-e2e, che porta SPENA_E2E=1 da .env.e2e. Qui manca, e non parto."
    )

import asyncio  # noqa: E402
import json  # noqa: E402
import uuid  # noqa: E402

from sqlalchemy import delete, select  # noqa: E402

from app.core.db import SessionLocal  # noqa: E402
from app.db.models.ingredient import Ingredient, IngredientCategory  # noqa: E402
from app.db.models.recipe import Recipe  # noqa: E402
from app.db.models.recipe_import import (  # noqa: E402
    GIALLOZAFFERANO,
    ImportState,
    ImportTerm,
    RecipeImport,
    TermDecision,
)
from app.repositories.imports import store_page, store_unparsable  # noqa: E402
from app.repositories.ingredients import create_ingredient, delete_ingredient_if_unused  # noqa: E402
from app.services.recipe_import.materialize import materialize_ready  # noqa: E402
from app.services.registry import recategorize_ingredient  # noqa: E402

# Il segno che porta ogni nome di questo file, e i prefissi di chiavi e indirizzi: la
# pulizia ritrova tutto da qui, e non tocca niente del seme.
NAME_MARK = "e2e-scartate"
KEY_PREFIX = f"{NAME_MARK}-"
URL_PREFIX = "https://e2e.invalid/scartate/"


async def seed(tag: str) -> dict:
    # Un titolo lungo come quelli veri: a 375px la riga lo tronca, e il tasto resta intero.
    title = (
        "Torta della nonna con crema pasticcera, pinoli tostati e scorza di limone "
        f"({NAME_MARK} {tag})"
    )
    async with SessionLocal() as session:
        farina = await create_ingredient(
            session, name=f"farina {NAME_MARK} {tag}",
            display_name=f"Farina {NAME_MARK} {tag}", category=IngredientCategory.CEREALI,
        )
        # la causa dello scarto: la panna finita per sbaglio fra i prodotti per la casa
        panna = await create_ingredient(
            session, name=f"panna {NAME_MARK} {tag}",
            display_name=f"Panna {NAME_MARK} {tag}", category=IngredientCategory.CASA,
        )
        righe = [
            (f"{KEY_PREFIX}{tag}-farina", f"Farina 00 {NAME_MARK} {tag}", farina.id, "300 g"),
            (f"{KEY_PREFIX}{tag}-panna", f"Panna fresca {NAME_MARK} {tag}", panna.id, "200 ml"),
        ]
        session.add_all([
            ImportTerm(
                source=GIALLOZAFFERANO, term_key=key, display_name=name, occurrences=1,
                decision=TermDecision.MAPPED, ingredient_id=ingredient_id,
                decided_by="human", created_ingredient=False,
            )
            for key, name, ingredient_id, _ in righe
        ])
        await session.flush()
        torta = await store_page(
            session, source=GIALLOZAFFERANO, url=f"{URL_PREFIX}{tag}/torta.html",
            payload={
                "title": title, "instructions": "Cuoci in forno.", "servings": 8,
                "ingredients": [
                    {"key": key, "name": name, "quantity_text": quantity}
                    for key, name, _, quantity in righe
                ],
            },
        )
        unreadable_url = (
            f"{URL_PREFIX}{tag}/una-pagina-senza-ricetta-con-un-indirizzo-lungo-come-quelli-veri.html"
        )
        await store_unparsable(
            session, source=GIALLOZAFFERANO, url=unreadable_url,
            reason="nessuna riga dd.gz-ingredient nella pagina",
        )
        await materialize_ready(session, GIALLOZAFFERANO)
        if torta.state != ImportState.SKIPPED:
            raise SystemExit(f"la semina non ha scartato la torta: {torta.state}")
        await session.commit()
        return {
            "title": title,
            "nonFood": panna.display_name,
            "nonFoodId": str(panna.id),
            "unreadableUrl": unreadable_url,
        }


async def fix(ingredient_id: str) -> dict:
    async with SessionLocal() as session:
        ingredient = await recategorize_ingredient(
            session, uuid.UUID(ingredient_id), IngredientCategory.LATTICINI
        )
        await session.commit()
        return {"fixed": ingredient.display_name, "category": ingredient.category}


async def clean() -> dict:
    async with SessionLocal() as session:
        pages = (
            await session.execute(
                delete(RecipeImport).where(RecipeImport.url.like(f"{URL_PREFIX}%"))
            )
        ).rowcount
        # una cancellazione vera e non l'archivio: sono ricette di prova, e le righe se ne
        # vanno con loro (`cascade`), così gli ingredienti qui sotto tornano liberi
        recipes = list(
            (
                await session.execute(
                    select(Recipe).where(Recipe.source_ref.like(f"{URL_PREFIX}%"))
                )
            ).scalars()
        )
        for recipe in recipes:
            await session.delete(recipe)
        terms = (
            await session.execute(
                delete(ImportTerm).where(ImportTerm.term_key.like(f"{KEY_PREFIX}%"))
            )
        ).rowcount
        await session.flush()
        ids = list(
            (
                await session.execute(
                    select(Ingredient.id).where(Ingredient.name.like(f"%{NAME_MARK}%"))
                )
            ).scalars()
        )
        # `delete_ingredient_if_unused` e non una cancellazione cieca: se qualcosa li usa
        # ancora, lo si dice invece di rompere un vincolo
        kept = [str(i) for i in ids if not await delete_ingredient_if_unused(session, i)]
        await session.commit()
        return {
            "pages": pages, "recipes": len(recipes), "terms": terms,
            "ingredients": len(ids) - len(kept), "kept": kept,
        }


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "seed" and len(sys.argv) == 3:
        print(json.dumps(asyncio.run(seed(sys.argv[2]))))
    elif command == "fix" and len(sys.argv) == 3:
        print(json.dumps(asyncio.run(fix(sys.argv[2]))))
    elif command == "clean":
        print(json.dumps(asyncio.run(clean())))
    else:
        raise SystemExit("uso: e2e_skipped_pages.py seed <etichetta> | fix <id-ingrediente> | clean")


if __name__ == "__main__":
    main()

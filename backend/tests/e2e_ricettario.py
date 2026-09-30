"""Semina e pulizia per le prove del ricettario in `frontend/e2e/style.spec.ts` (T3
Consegna 4). Non è un test di pytest.

Il seme dello stack e2e porta ricette senza foto e senza categoria, e nessuna rotta
scrive `image_url` o una categoria nuova (`_check_category` accetta solo quelle che il
ricettario ha già). Le prove della miniatura e del pannello «Filtri» ne hanno bisogno:
questo file scrive tre ricette con le loro righe dal repository vero (`create_recipe`),
e i quattro ingredienti che nominano. Le foto puntano a `https://foto.e2e.invalid/`, un
dominio che non esiste: le serve la prova con `page.route`, e nessuna richiesta esce.

Le tre ricette, tutte nella categoria `E2E ricettario <etichetta>` e con ingredienti che
la dispensa non ha:

- «con foto»: zucchina, carota e branzino principali → reparto `verdura`, mancano 3;
- «senza foto»: branzino principale, zucchina secondaria → reparto `pesce`, mancano 2;
- «foto rotta»: manzo principale → reparto `carne`, manca 1.

Si lancia dentro il container del backend, dove `./backend` è montato su `/app`:

    $E2E exec -T backend python tests/e2e_ricettario.py seed <etichetta>
    $E2E exec -T backend python tests/e2e_ricettario.py clean

`seed` stampa su stdout, in JSON, cosa ha scritto. `clean` toglie ricette e ingredienti
di questo file, anche quelli di un giro interrotto, e si può chiamare prima di seminare.

Scrive e cancella nel database, quindi **si rifiuta di partire fuori dallo stack e2e**:
vuole `SPENA_E2E=1`, che sta solo in `.env.e2e`.

Non si chiama `test_*.py` apposta: pytest non lo raccoglie.
"""

import os
import sys

if os.environ.get("SPENA_E2E") != "1":
    raise SystemExit(
        "e2e_ricettario.py scrive e cancella nel database: gira solo sullo stack "
        "spena-e2e, che porta SPENA_E2E=1 da .env.e2e. Qui manca, e non parto."
    )

import asyncio  # noqa: E402
import json  # noqa: E402

from sqlalchemy import select  # noqa: E402

from app.core.db import SessionLocal  # noqa: E402
from app.db.models.ingredient import Ingredient, IngredientCategory  # noqa: E402
from app.db.models.recipe import Recipe  # noqa: E402
from app.repositories.ingredients import create_ingredient, delete_ingredient_if_unused  # noqa: E402
from app.repositories.recipes import create_recipe  # noqa: E402

TITLE_PREFIX = "Ricettario e2e"
# il segno nel nome di ogni ingrediente di questo file: la pulizia li ritrova da qui
NAME_MARK = "e2e-ricettario"
PHOTOS = "https://foto.e2e.invalid"


async def seed(tag: str) -> dict:
    category = f"E2E ricettario {tag}"
    async with SessionLocal() as session:
        made: dict[str, Ingredient] = {}
        for key, department in (
            ("zucchina", IngredientCategory.VERDURA),
            ("carota", IngredientCategory.VERDURA),
            ("branzino", IngredientCategory.PESCE),
            ("manzo", IngredientCategory.CARNE),
        ):
            made[key] = await create_ingredient(
                session,
                name=f"{key} {NAME_MARK} {tag}",
                display_name=f"{key.capitalize()} {NAME_MARK} {tag}",
                category=department,
            )

        async def recipe(title: str, lines: list[tuple[str, str]], image_url: str | None) -> Recipe:
            created = await create_recipe(
                session,
                title=f"{TITLE_PREFIX} {title} {tag}",
                description=None,
                instructions="1. Prova.",
                servings=2,
                source="manual",
                source_ref=None,
                ingredients=[(made[key].id, role, None, None) for key, role in lines],
                embedding=None,
                category=category,
            )
            created.image_url = image_url
            return created

        con_foto = await recipe(
            "con foto",
            [("zucchina", "primary"), ("carota", "primary"), ("branzino", "primary")],
            f"{PHOTOS}/{tag}/buona.png",
        )
        senza_foto = await recipe(
            "senza foto", [("branzino", "primary"), ("zucchina", "secondary")], None
        )
        foto_rotta = await recipe("foto rotta", [("manzo", "primary")], f"{PHOTOS}/{tag}/rotta.png")
        await session.commit()
        return {
            "categoria": category,
            "conFoto": {"id": str(con_foto.id), "title": con_foto.title},
            "senzaFoto": {"id": str(senza_foto.id), "title": senza_foto.title},
            "fotoRotta": {"id": str(foto_rotta.id), "title": foto_rotta.title},
            "ingrediente": made["branzino"].display_name,
        }


async def clean() -> dict:
    async with SessionLocal() as session:
        recipes = list(
            (
                await session.execute(select(Recipe).where(Recipe.title.like(f"{TITLE_PREFIX} %")))
            ).scalars()
        )
        # una cancellazione vera e non l'archivio: sono ricette di prova, e le righe se ne
        # vanno con loro (`cascade`), così gli ingredienti qui sotto tornano liberi
        for recipe in recipes:
            await session.delete(recipe)
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
        return {"recipes": len(recipes), "ingredients": len(ids) - len(kept), "kept": kept}


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "seed" and len(sys.argv) == 3:
        print(json.dumps(asyncio.run(seed(sys.argv[2]))))
    elif command == "clean":
        print(json.dumps(asyncio.run(clean())))
    else:
        raise SystemExit("uso: e2e_ricettario.py seed <etichetta> | clean")


if __name__ == "__main__":
    main()

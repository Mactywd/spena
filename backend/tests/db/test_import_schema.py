"""Lo schema dell'import difende da solo le tre cose che il codice non può.

Un termine «collegato» a niente, uno stato inventato e due volte la stessa pagina
sono difetti che arrivano silenziosi: il primo produce ricette con una riga in
meno, cioè una disponibilità calcolata su una ricetta che non è quella scritta.
"""

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.models.recipe_import import GIALLOZAFFERANO, ImportTerm, RecipeImport


def una_pagina(url: str = "https://ricette.giallozafferano.it/Tiramisu.html") -> RecipeImport:
    return RecipeImport(
        source=GIALLOZAFFERANO, url=url, payload={"title": "Tiramisù"}, state="pending"
    )


async def test_un_termine_collegato_deve_avere_un_ingrediente(db_session):
    db_session.add(
        ImportTerm(
            source=GIALLOZAFFERANO, term_key="ricette-con-i-Rigatoni",
            display_name="Rigatoni", occurrences=3, decision="mapped",
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_un_termine_ignorato_non_ha_bisogno_di_ingrediente(db_session):
    db_session.add(
        ImportTerm(
            source=GIALLOZAFFERANO, term_key="ricette-con-Acqua",
            display_name="Acqua", occurrences=7, decision="ignored",
        )
    )
    await db_session.flush()


async def test_una_decisione_inventata_e_rifiutata(db_session):
    db_session.add(
        ImportTerm(
            source=GIALLOZAFFERANO, term_key="ricette-con-il-Burro",
            display_name="Burro", occurrences=1, decision="quasi",
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_un_ruolo_corretto_a_mano_puo_solo_essere_uno_dei_due(db_session):
    db_session.add(
        ImportTerm(
            source=GIALLOZAFFERANO, term_key="ricette-con-l-Aglio",
            display_name="Aglio", occurrences=9, decision="pending",
            role_override="accessorio",
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_la_stessa_pagina_non_entra_due_volte(db_session):
    db_session.add(una_pagina())
    await db_session.flush()
    db_session.add(una_pagina())
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_uno_stato_inventato_e_rifiutato(db_session):
    pagina = una_pagina("https://ricette.giallozafferano.it/Carbonara.html")
    pagina.state = "quasi-importata"
    db_session.add(pagina)
    with pytest.raises(IntegrityError):
        await db_session.flush()

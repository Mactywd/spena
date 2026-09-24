from sqlalchemy import select

from app.cli.drop_seed_recipes import SEED_SOURCE_REF, drop_seed_recipes
from app.db.models.recipe import CookingEvent, Recipe


def _ricetta(titolo: str, source: str, source_ref: str | None) -> Recipe:
    return Recipe(title=titolo, instructions="Cuoci.", source=source, source_ref=source_ref)


async def _prepara(db_session):
    seme = _ricetta("Pasta al pomodoro", "dataset", SEED_SOURCE_REF)
    importata = _ricetta("Amatriciana", "dataset", "https://ricette.giallozafferano.it/A.html")
    scritta = _ricetta("Bozza", "ai", None)
    db_session.add_all([seme, importata, scritta])
    await db_session.flush()
    db_session.add(CookingEvent(recipe_id=seme.id, snapshot={"title": seme.title}))
    await db_session.flush()
    return seme, importata, scritta


async def _titoli(db_session) -> set[str]:
    return set((await db_session.execute(select(Recipe.title))).scalars())


async def test_senza_conferma_dice_cosa_toglierebbe_e_non_tocca_niente(db_session):
    await _prepara(db_session)
    righe: list[str] = []

    cancellate = await drop_seed_recipes(db_session, confirm=False, log=righe.append)

    assert cancellate == 0
    assert await _titoli(db_session) == {"Pasta al pomodoro", "Amatriciana", "Bozza"}
    testo = "\n".join(righe)
    assert "Pasta al pomodoro" in testo
    assert "Amatriciana" not in testo
    assert "1 cottura" in testo
    assert "--conferma" in testo


async def test_con_conferma_toglie_solo_quelle_di_semina(db_session):
    await _prepara(db_session)

    cancellate = await drop_seed_recipes(db_session, confirm=True, log=lambda _: None)

    assert cancellate == 1
    assert await _titoli(db_session) == {"Amatriciana", "Bozza"}
    # la cottura resta nello storico, con la sua fotografia, senza ricetta collegata
    evento = (await db_session.execute(select(CookingEvent))).scalar_one()
    await db_session.refresh(evento)
    assert evento.recipe_id is None
    assert evento.snapshot == {"title": "Pasta al pomodoro"}


async def test_rilanciarlo_non_trova_piu_niente(db_session):
    await _prepara(db_session)
    await drop_seed_recipes(db_session, confirm=True, log=lambda _: None)

    assert await drop_seed_recipes(db_session, confirm=True, log=lambda _: None) == 0


async def test_il_marchio_e_quello_che_il_seme_scrive_davvero():
    """Il comando riconosce le ricette di semina da `source_ref`: se il seme un
    giorno scrivesse un altro valore, il comando non troverebbe più niente e
    direbbe «niente da togliere» mentre sono tutte lì."""
    import json

    from app.cli.seed import RECIPES_FILE, find_data_dir

    ricette = json.loads((find_data_dir() / RECIPES_FILE).read_text())
    assert {r.get("source_ref") for r in ricette} == {SEED_SOURCE_REF}

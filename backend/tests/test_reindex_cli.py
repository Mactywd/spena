import pytest
from sqlalchemy import select

from app.cli.reindex import main, reindex
from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.recipe import Recipe
from app.db.models.recipe import EMBEDDING_DIM
from app.repositories.recipes import create_recipe


async def una_ricetta(db_session, titolo: str, embedding: list[float] | None) -> Recipe:
    ingrediente = Ingredient(
        name=titolo.lower(), display_name=titolo, category=IngredientCategory.ALTRO
    )
    db_session.add(ingrediente)
    await db_session.flush()
    return await create_recipe(
        db_session, title=titolo, description="Breve", instructions="Cuoci.",
        servings=2, source="dataset", source_ref=None,
        ingredients=[(ingrediente.id, "primary", "1", None)], embedding=embedding,
    )


async def test_scrive_i_vettori_mancanti(db_session):
    await una_ricetta(db_session, "Senza", None)

    scritti = await reindex(db_session)

    assert scritti == 1
    ricetta = (await db_session.execute(select(Recipe))).scalars().one()
    assert ricetta.embedding is not None
    assert len(ricetta.embedding) == EMBEDDING_DIM


async def test_lascia_in_pace_i_vettori_che_ci_sono(db_session):
    presente = [0.5] * EMBEDDING_DIM
    await una_ricetta(db_session, "Con", presente)

    scritti = await reindex(db_session)

    assert scritti == 0
    ricetta = (await db_session.execute(select(Recipe))).scalars().one()
    assert list(ricetta.embedding) == pytest.approx(presente)


async def test_su_un_ricettario_gia_completo_non_fa_niente(db_session):
    assert await reindex(db_session) == 0


async def test_senza_modello_lo_dice_invece_di_tacere(db_session, monkeypatch):
    """Un comando che «riesce» scrivendo zero vettori è indistinguibile da uno che
    non serviva: la differenza va detta, ed è il motivo per cui l'eccezione risale."""
    from app.services.embeddings import EmbeddingUnavailable

    await una_ricetta(db_session, "Senza", None)

    class ProviderRotto:
        async def embed_passages(self, texts):
            raise EmbeddingUnavailable("modello non installato")

        async def embed_query(self, text):
            raise EmbeddingUnavailable("modello non installato")

    monkeypatch.setattr("app.cli.reindex.get_embedding_provider", lambda: ProviderRotto())

    with pytest.raises(EmbeddingUnavailable):
        await reindex(db_session)


class _SessioneFinta:
    """`SessionLocal()` nel test: consegna la sessione della fixture invece di
    aprirne una vera, così `main()` gira contro la stessa transazione annullabile
    che usano tutti gli altri test."""

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc_info):
        return False


async def test_main_senza_modello_non_esplode_e_dice_come_accenderlo(
    db_session, monkeypatch, capsys
):
    """Il finding del reviewer: `main()` non aveva nessun try/except attorno a
    `reindex()`, quindi l'eccezione saliva fino a `asyncio.run` come un traceback
    inglese. Qui deve invece uscire senza eccezione e stampare l'italiano che nomina
    `INSTALL_EMBEDDINGS=1`, la stessa frase di `SEMANTIC_OFF_HOWTO`."""
    from app.services.embeddings import EmbeddingUnavailable

    await una_ricetta(db_session, "Senza", None)

    class ProviderRotto:
        async def embed_passages(self, texts):
            raise EmbeddingUnavailable("modello non installato")

        async def embed_query(self, text):
            raise EmbeddingUnavailable("modello non installato")

    monkeypatch.setattr("app.cli.reindex.get_embedding_provider", lambda: ProviderRotto())
    monkeypatch.setattr("app.cli.reindex.SessionLocal", lambda: _SessioneFinta(db_session))

    await main()  # non deve risalire nessuna eccezione

    stampato = capsys.readouterr().out
    assert "INSTALL_EMBEDDINGS=1" in stampato

    # non ha scritto nulla: il giro è fallito per intero, non a metà
    ricetta = (await db_session.execute(select(Recipe))).scalars().one()
    assert ricetta.embedding is None

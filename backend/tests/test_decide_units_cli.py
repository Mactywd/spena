"""L'undo di una decisione dell'AI sulle unità."""

from sqlalchemy import select

from app.db.models.unit import Unit
from app.repositories.units import reset_unit


async def test_azzerare_riporta_una_unita_a_non_decisa(db_session):
    """L'undo di una decisione AI: la chiamata successiva la ridecide."""
    db_session.add(
        Unit(key="costa", singular="costa", plural="cost", decided_by="ai")
    )
    await db_session.flush()

    assert await reset_unit(db_session, "costa") is True

    costa = (await db_session.execute(select(Unit).where(Unit.key == "costa"))).scalars().one()
    assert costa.decided_by is None and costa.singular is None and costa.plural is None


async def test_azzerare_una_chiave_che_non_esiste_lo_dice(db_session):
    assert await reset_unit(db_session, "inesistente") is False

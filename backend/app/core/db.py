from collections.abc import AsyncIterator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


# SQLSTATE di Postgres: 23503 = violazione di chiave esterna, 23505 = unicità.
# Distinguerli serve perché sono due risposte diverse: un riferimento pendente è
# "non trovato" (404), un duplicato è "conflitto" (409).
#
# Servono entrambi i predicati, e nominati: un `else` che tratta come duplicato
# tutto ciò che non è un riferimento pendente inghiotte anche 23502 (not-null) e
# 23514 (i check constraint `ck_recipe_ingredient_role`, `ck_recipe_source`).
# Quelle violazioni non sono un gesto dell'utente: sono un difetto nostro — enum
# Pydantic e vincolo divergenti, per esempio — e devono restare visibili come 500
# invece di mandare il proprietario a cercare un doppione che non esiste.
FOREIGN_KEY_VIOLATION = "23503"
UNIQUE_VIOLATION = "23505"


def is_missing_reference(error: IntegrityError) -> bool:
    """Vero se l'IntegrityError nasce da un id che non esiste, non da un duplicato."""
    return getattr(error.orig, "sqlstate", None) == FOREIGN_KEY_VIOLATION


def is_unique_violation(error: IntegrityError) -> bool:
    """Vero se l'IntegrityError nasce da un duplicato, non da altro."""
    return getattr(error.orig, "sqlstate", None) == UNIQUE_VIOLATION

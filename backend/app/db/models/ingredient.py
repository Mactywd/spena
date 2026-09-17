import uuid
from enum import StrEnum

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.core.db import Base
from app.db.models.base import TimestampMixin, UUIDMixin
from app.domain.rules import kind_for_category

# La larghezza delle tre colonne che portano un nome di ingrediente: il nome canonico,
# il nome visibile e un alias. Ha un nome perché chi scrive in quelle colonne deve
# poter rifiutare una stringa troppo lunga *prima* dell'insert — oltre il limite
# l'errore arriva dal database in mezzo a una passata che ha già scritto — e un 120
# ricopiato in ogni punto di scrittura si scollerebbe da qui al primo allargamento.
NAME_MAX_LENGTH = 120


class IngredientCategory(StrEnum):
    """Reparti del supermercato: guidano il raggruppamento della lista."""

    VERDURA = "verdura"
    FRUTTA = "frutta"
    CARNE = "carne"
    PESCE = "pesce"
    LATTICINI = "latticini"
    CEREALI = "cereali"
    LEGUMI = "legumi"
    CONDIMENTI = "condimenti"
    SPEZIE = "spezie"
    BEVANDE = "bevande"
    DOLCI = "dolci"
    ALTRO = "altro"
    # I due reparti non alimentari. Stanno nello stesso enum e non in uno separato
    # perché sono corsie di supermercato come le altre, e la lista li raggruppa
    # allo stesso modo; a separarli è `kind_for_category` nel dominio, che è
    # l'unica cosa che le guardie leggono.
    CASA = "casa"
    IGIENE = "igiene"


class Ingredient(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "ingredients"
    # dichiarato qui e non solo nella migrazione: l'autogenerate confronta i
    # modelli con il database e cancellerebbe ogni indice che i modelli non
    # conoscono, autocomplete trigram compreso
    __table_args__ = (
        Index(
            "ix_ingredients_name_trgm", "name",
            postgresql_using="gin", postgresql_ops={"name": "gin_trgm_ops"},
        ),
    )

    name: Mapped[str] = mapped_column(String(NAME_MAX_LENGTH), unique=True)
    display_name: Mapped[str] = mapped_column(String(NAME_MAX_LENGTH))
    category: Mapped[str] = mapped_column(String(20))
    # Se questa voce è cibo. Derivata da `category` e mai scritta a mano: l'unico
    # posto che la calcola è `kind_for_category` nel dominio, e l'unico che la
    # scrive è il validator `_deduce_kind` qui sotto, che scatta su ogni
    # assegnazione di `category` — nel costruttore quanto in una riassegnazione
    # successiva, così spostare un ingrediente da un reparto alimentare a «casa»
    # sposta con sé il suo kind. Memorizzata invece che calcolata a ogni lettura
    # perché le guardie e i filtri sono SQL: `WHERE kind = 'food'` sta in un
    # posto, mentre la partizione dei reparti ricopiata in ogni query si
    # scollerebbe al terzo reparto.
    kind: Mapped[str] = mapped_column(String(10))
    # popolato in fase 3, quando arrivano le tabelle di composizione
    composition_ref: Mapped[str | None] = mapped_column(String(60), nullable=True)

    aliases: Mapped[list["IngredientAlias"]] = relationship(
        back_populates="ingredient", cascade="all, delete-orphan", lazy="selectin"
    )

    @validates("category")
    def _deduce_kind(self, key: str, category: str) -> str:
        """Fa in modo che `kind` discenda sempre da `category`, per ogni scrittore.

        `create_ingredient` non passa un `kind`: lo deduce questo hook, che si
        attiva su qualunque costruzione o riassegnazione di `category` — quindi
        anche sul seme e sui test che costruiscono `Ingredient(...)` a mano,
        nessuno dei quali conosce `kind_for_category`. Un secondo scrittore di
        `kind` è la via con cui una riga «igiene ma è cibo» potrebbe nascere.
        """
        self.kind = kind_for_category(category)
        return category


class IngredientAlias(UUIDMixin, Base):
    __tablename__ = "ingredient_aliases"
    __table_args__ = (
        UniqueConstraint("ingredient_id", "alias"),
        Index(
            "ix_aliases_alias_trgm", "alias",
            postgresql_using="gin", postgresql_ops={"alias": "gin_trgm_ops"},
        ),
    )

    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ingredients.id", ondelete="CASCADE")
    )
    alias: Mapped[str] = mapped_column(String(NAME_MAX_LENGTH))
    source: Mapped[str] = mapped_column(String(20))

    ingredient: Mapped[Ingredient] = relationship(back_populates="aliases")

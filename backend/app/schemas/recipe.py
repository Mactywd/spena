import uuid

from pydantic import BaseModel, Field, model_validator

from app.db.models.ingredient import IngredientCategory
from app.db.models.recipe import RecipeSource
from app.domain.rules import Availability, IngredientRole


class RecipeIngredientIn(BaseModel):
    """Un ingrediente esistente, o uno da creare salvando.

    Le due forme stanno in un modello solo perché il salvataggio è uno: due schemi
    separati significherebbero due rotte, o un `Union` che il frontend deve scegliere
    riga per riga. Il validatore è ciò che tiene onesta la scelta.
    """

    ingredient_id: uuid.UUID | None = None
    name: str | None = Field(default=None, max_length=120)
    category: IngredientCategory | None = None
    role: IngredientRole
    quantity_text: str | None = Field(default=None, max_length=100)
    note: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def _one_of_the_two(self) -> "RecipeIngredientIn":
        if self.ingredient_id is not None:
            return self
        if not self.name:
            raise ValueError("serve `ingredient_id`, oppure `name` con `category`")
        if self.category is None:
            # indovinare «altro» popolerebbe il registro di voci che nessuno correggerà
            raise ValueError("per creare un ingrediente serve anche `category`")
        return self


class RecipeCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    instructions: str = Field(min_length=1)
    servings: int | None = Field(default=None, ge=1, le=50)
    source: RecipeSource
    source_ref: str | None = Field(default=None, max_length=500)
    ingredients: list[RecipeIngredientIn] = Field(default_factory=list)


class RecipeIngredientOut(BaseModel):
    ingredient_id: uuid.UUID
    ingredient_name: str
    role: IngredientRole
    quantity_text: str | None
    note: str | None
    availability: Availability
    satisfied: bool
    # quel che va mostrato: a 1× è quantity_text, riscritto solo quando si riporziona
    quantity_display: str | None
    quantity_scaled: bool


class RecipeOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    instructions: str
    servings: int | None
    source: str
    source_ref: str | None
    ingredients: list[RecipeIngredientOut]
    missing: int
    cookable: bool
    # I nomi di quel che manca, in ordine alfabetico. Su RecipeOut è ridondante — le
    # righe portano già `availability` e `satisfied`, e nessuna schermata lo legge —
    # ed è voluto: nel frontend `RecipeDetail extends RecipeSummary`, quindi un campo
    # che solo la scheda riassuntiva manda renderebbe obbligatorio sul dettaglio
    # qualcosa che il dettaglio non manda, e `tsc` lo direbbe solo a `npm run build`.
    missing_names: list[str] = []
    # stesse quattro righe di RecipeSummaryOut: RecipeOut non eredita da lei oggi,
    # e introdurre una gerarchia per risparmiarle non sarebbe YAGNI rispettato
    image_url: str | None = None
    prep_minutes: int | None = None
    cook_minutes: int | None = None
    category: str | None = None
    scaled_to: int | None = None
    unscalable_lines: int = 0
    # il denominatore di `unscalable_lines`: quante righe una dose ce l'hanno. Lo
    # manda il server perché è il server a saperlo — `len(ingredients)` conterebbe
    # anche le righe senza `quantity_text`, che non sono dosi mancate
    dose_lines: int = 0


class RecipeSummaryOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    source: str
    missing: int
    cookable: bool
    # I nomi di quel che manca, in ordine alfabetico. Su RecipeOut è ridondante — le
    # righe portano già `availability` e `satisfied`, e nessuna schermata lo legge —
    # ed è voluto: nel frontend `RecipeDetail extends RecipeSummary`, quindi un campo
    # che solo la scheda riassuntiva manda renderebbe obbligatorio sul dettaglio
    # qualcosa che il dettaglio non manda, e `tsc` lo direbbe solo a `npm run build`.
    missing_names: list[str] = []
    image_url: str | None = None
    prep_minutes: int | None = None
    cook_minutes: int | None = None
    category: str | None = None


class SearchModeOut(BaseModel):
    """Se la ricerca del ricettario è ibrida o solo testuale, in questo momento.

    La spec §11 vuole un avviso discreto quando il modello di embedding non si
    carica. Sta in una rotta sua e non nella risposta di /recipes/search perché
    quella è un elenco e incartarla cambierebbe un contratto che funziona; lo schermo
    Ricette la chiede una volta e mostra la riga se `semantic` è falso.
    """

    semantic: bool

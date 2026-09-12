"""Lettura di una pagina di ricetta di GialloZafferano.

Il parsing è puro: prende il testo della pagina e non sa da dove arriva. È quel che
permetterà al futuro «incolla un link» di riusarlo senza modifiche.

Perché non serve nessun modello linguistico: la pagina porta un blocco
schema.org/Recipe, e nel corpo tiene il nome dell'ingrediente e la quantità in due
elementi separati, con un indirizzo stabile per ogni ingrediente del loro catalogo.
Il nome non va estratto da una stringa: è un elemento.
"""

import html as html_entities
import json
import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

# Un rimando fotografico è un numero isolato da spazi su entrambi i lati, prima
# della punteggiatura o a fine paragrafo. Lo spazio a sinistra **e** a destra è ciò
# che distingue «per 5 minuti 2 .» da «dividete l'impasto in 4.»: la seconda è
# prosa, e una regola più generosa la mangerebbe.
PHOTO_REFERENCES_BEFORE_PUNCTUATION = re.compile(r"(?:\s\d{1,2})+\s+(?=[.,;:])")
PHOTO_REFERENCES_AT_END = re.compile(r"(?:\s\d{1,2})+\s*$")


def strip_photo_references(text: str) -> str:
    """Via i rimandi alle fotografie, che qui non ci sono."""
    cleaned = text.replace("\xa0", " ")
    cleaned = PHOTO_REFERENCES_BEFORE_PUNCTUATION.sub("", cleaned)
    cleaned = PHOTO_REFERENCES_AT_END.sub("", cleaned)
    return cleaned.strip()


def normalize_steps(raw: object) -> list[str]:
    """`recipeInstructions` arriva in tre forme, e tutte e tre sono nei dati veri.

    Lista di paragrafi, lista di oggetti `HowToStep` con il testo dentro, o una
    stringa sola. Una forma non gestita non solleverebbe niente: produrrebbe una
    ricetta senza procedimento, che è peggio.
    """
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        steps: list[str] = []
        for entry in raw:
            if isinstance(entry, str):
                steps.append(entry)
            elif isinstance(entry, dict) and isinstance(entry.get("text"), str):
                steps.append(entry["text"])
        return steps
    return []


def clean_instructions(raw: object) -> str:
    """I passaggi ripuliti, uniti da una riga vuota."""
    steps = [strip_photo_references(step) for step in normalize_steps(raw)]
    return "\n\n".join(step for step in steps if step)


MAX_QUANTITY_CHARS = 100  # il limite di recipe_ingredients.quantity_text
MIN_SERVINGS = 1
MAX_SERVINGS = 50  # i limiti che RecipeCreate già impone


class UnparsablePage(Exception):
    """La pagina non è una ricetta leggibile, e il motivo va conservato.

    Una pagina che sparisce in silenzio è un import di cui non si può dire niente:
    il motivo finisce in `recipe_imports.skipped_reason` e il riepilogo del comando
    li conta.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class ParsedIngredient:
    key: str
    name: str
    quantity_text: str | None


@dataclass(frozen=True)
class ParsedRecipe:
    title: str
    description: str | None
    instructions: str
    servings: int | None
    category: str | None
    image_url: str | None
    prep_minutes: int | None
    cook_minutes: int | None
    ingredients: list[ParsedIngredient] = field(default_factory=list)
    nutrition: dict | None = None

    def as_payload(self) -> dict:
        """La forma che finisce in `recipe_imports.payload`, serializzabile in JSON."""
        return {
            "title": self.title,
            "description": self.description,
            "instructions": self.instructions,
            "servings": self.servings,
            "category": self.category,
            "image_url": self.image_url,
            "prep_minutes": self.prep_minutes,
            "cook_minutes": self.cook_minutes,
            "ingredients": [
                {"key": i.key, "name": i.name, "quantity_text": i.quantity_text}
                for i in self.ingredients
            ],
            "nutrition": self.nutrition,
        }


ISO_DURATION = re.compile(r"^P(?:(?P<days>\d+)D)?T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?")


def iso_minutes(value: object) -> int | None:
    """`PT1H30M` sono 90 minuti. Un formato che non riconosco è nessun minuto."""
    if not isinstance(value, str):
        return None
    found = ISO_DURATION.match(value.strip())
    if found is None:
        return None
    days = int(found.group("days") or 0)
    hours = int(found.group("hours") or 0)
    minutes = int(found.group("minutes") or 0)
    total = days * 24 * 60 + hours * 60 + minutes
    return total or None


def servings_from(value: object) -> int | None:
    """`4`, `"4"`, `"10 porzioni"`: il primo intero, se è un numero di porzioni sensato."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        candidate = value
    elif isinstance(value, list) and value:
        return servings_from(value[0])
    elif isinstance(value, str):
        found = re.search(r"\d+", value)
        if found is None:
            return None
        candidate = int(found.group())
    else:
        return None
    return candidate if MIN_SERVINGS <= candidate <= MAX_SERVINGS else None


def image_url_from(value: object) -> str | None:
    """`image` è una stringa, una lista, o un oggetto con `url`. Tutte e tre."""
    if isinstance(value, str):
        return value or None
    if isinstance(value, list):
        return image_url_from(value[0]) if value else None
    if isinstance(value, dict):
        return image_url_from(value.get("url"))
    return None


def recipe_jsonld(soup: BeautifulSoup) -> dict:
    """Il blocco schema.org/Recipe, cercato in tutte le forme che la fonte usa.

    Un oggetto solo, una lista di oggetti, o un `@graph`: saltarne una vorrebbe dire
    scartare pagine perfettamente leggibili.
    """
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        candidates = data if isinstance(data, list) else [data]
        if isinstance(data, dict) and isinstance(data.get("@graph"), list):
            candidates = data["@graph"]
        for entry in candidates:
            if not isinstance(entry, dict):
                continue
            entry_type = entry.get("@type")
            types = entry_type if isinstance(entry_type, list) else [entry_type]
            if "Recipe" in types:
                return entry
    raise UnparsablePage("nessun blocco schema.org/Recipe nella pagina")


def term_key(href: str | None, name: str) -> str:
    """L'identità del termine è l'indirizzo del loro catalogo, non il nome scritto.

    Un refuso corretto cambia il nome e non l'indirizzo, e un dizionario costruito
    sui nomi perderebbe la decisione già presa. Le righe senza link — il catalogo
    non copre tutto — ricadono sul nome, marcate perché si veda che è un ripiego.
    """
    if href:
        return href.strip("/")
    return f"testo:{name.strip().lower()}"


def parse_ingredients(soup: BeautifulSoup) -> list[ParsedIngredient]:
    """Tutte le righe `dd.gz-ingredient`, nell'ordine, intestazioni dei gruppi ignorate.

    Non si collassa niente qui: lo stesso termine può comparire due volte nella
    stessa ricetta (la frolla e la crema vogliono entrambe lo zucchero a velo), e
    collassare richiede di sapere su quale ingrediente finiscono, che il parser non
    sa. Lo fa la materializzazione.
    """
    rows = soup.select("dd.gz-ingredient")
    if not rows:
        raise UnparsablePage("nessuna riga dd.gz-ingredient nella pagina")

    ingredients: list[ParsedIngredient] = []
    for row in rows:
        link = row.find("a")
        quantity_tag = row.find("span")
        quantity = quantity_tag.get_text(" ", strip=True) if quantity_tag else ""
        if quantity_tag is not None:
            quantity_tag.extract()
        name = link.get_text(" ", strip=True) if link else row.get_text(" ", strip=True)
        name = html_entities.unescape(name).strip()
        if not name:
            continue
        quantity = html_entities.unescape(quantity).strip()[:MAX_QUANTITY_CHARS]
        ingredients.append(
            ParsedIngredient(
                key=term_key(link.get("href") if link else None, name),
                name=name,
                quantity_text=quantity or None,
            )
        )
    if not ingredients:
        raise UnparsablePage("le righe degli ingredienti non hanno nomi leggibili")
    return ingredients


def parse_recipe(html: str) -> ParsedRecipe:
    """Il testo di una pagina → una ricetta leggibile, o `UnparsablePage` col perché.

    Funzione pura: nessuna rete, nessun database. È il nucleo verificabile di tutto
    l'import, ed è ciò che il futuro «incolla un link» riuserà così com'è.
    """
    soup = BeautifulSoup(html, "html.parser")
    data = recipe_jsonld(soup)

    title = str(data.get("name") or "").strip()
    if not title:
        raise UnparsablePage("la ricetta non ha un titolo")

    description = str(data.get("description") or "").strip() or None
    instructions = clean_instructions(data.get("recipeInstructions"))
    category = str(data.get("recipeCategory") or "").strip() or None

    return ParsedRecipe(
        title=title,
        description=description,
        instructions=instructions,
        servings=servings_from(data.get("recipeYield")),
        category=category,
        image_url=image_url_from(data.get("image")),
        prep_minutes=iso_minutes(data.get("prepTime")),
        cook_minutes=iso_minutes(data.get("cookTime")),
        ingredients=parse_ingredients(soup),
        nutrition=data.get("nutrition") if isinstance(data.get("nutrition"), dict) else None,
    )

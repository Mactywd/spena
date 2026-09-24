"""Vocabolario dei nutrienti di Spena. Modulo puro: nessun accesso al database.

`products.nutrients` (e un domani un campo simile per l'ingrediente generico)
è un JSONB libero: qualunque chiave ci sta. Questo modulo fissa una volta sola
quali chiavi esistono, con che etichetta italiana, che unità, e il valore
nutritivo di riferimento (VNR) per un adulto secondo l'Allegato XIII, parti A
e B, del Regolamento UE 1169/2011 — la stessa normativa dell'etichetta
nutrizionale italiana. Non tutti i campi qui elencati sono raccolti oggi:
`COLLECTED_FIELDS` segna quelli che una fonte reale popola (vedi
`app.services.openfoodfacts._NUTRIENT_MAP`); gli altri restano nel vocabolario
in attesa di una fonte, così un domani si aggiunge una riga alla mappa e non
uno schema.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class NutrientField:
    label: str
    unit: str
    vnr: float | None  # valore nutritivo di riferimento, adulto medio; None = nessuno normato dal regolamento


NUTRIENT_FIELDS: dict[str, NutrientField] = {
    # macronutrienti — Allegato XIII, parte A (base 2000 kcal)
    "kcal": NutrientField("Energia", "kcal", 2000),
    "protein": NutrientField("Proteine", "g", 50),
    "carbs": NutrientField("Carboidrati", "g", 260),
    "sugars": NutrientField("di cui zuccheri", "g", 90),
    "fat": NutrientField("Grassi", "g", 70),
    "saturated_fat": NutrientField("di cui saturi", "g", 20),
    "fiber": NutrientField("Fibre", "g", None),
    "salt": NutrientField("Sale", "g", 6),
    # vitamine — Allegato XIII, parte B
    "vitamin_a": NutrientField("Vitamina A", "µg", 800),
    "vitamin_d": NutrientField("Vitamina D", "µg", 5),
    "vitamin_e": NutrientField("Vitamina E", "mg", 12),
    "vitamin_k": NutrientField("Vitamina K", "µg", 75),
    "vitamin_c": NutrientField("Vitamina C", "mg", 80),
    "thiamin": NutrientField("Tiamina (B1)", "mg", 1.1),
    "riboflavin": NutrientField("Riboflavina (B2)", "mg", 1.4),
    "niacin": NutrientField("Niacina (B3)", "mg", 16),
    "vitamin_b6": NutrientField("Vitamina B6", "mg", 1.4),
    "folate": NutrientField("Folati (B9)", "µg", 200),
    "vitamin_b12": NutrientField("Vitamina B12", "µg", 2.5),
    "biotin": NutrientField("Biotina", "µg", 50),
    "pantothenic_acid": NutrientField("Acido pantotenico", "mg", 6),
    # minerali — Allegato XIII, parte B
    "potassium": NutrientField("Potassio", "mg", 2000),
    "chloride": NutrientField("Cloruro", "mg", 800),
    "calcium": NutrientField("Calcio", "mg", 800),
    "phosphorus": NutrientField("Fosforo", "mg", 700),
    "magnesium": NutrientField("Magnesio", "mg", 375),
    "iron": NutrientField("Ferro", "mg", 14),
    "zinc": NutrientField("Zinco", "mg", 10),
    "copper": NutrientField("Rame", "mg", 1),
    "manganese": NutrientField("Manganese", "mg", 2),
    "fluoride": NutrientField("Fluoruro", "mg", 3.5),
    "selenium": NutrientField("Selenio", "µg", 55),
    "chromium": NutrientField("Cromo", "µg", 40),
    "molybdenum": NutrientField("Molibdeno", "µg", 50),
    "iodine": NutrientField("Iodio", "µg", 150),
}

# i campi che una fonte reale popola oggi (Open Food Facts, livello prodotto).
# Gli altri restano nel vocabolario sopra e basta: nessuna fonte li riempie
# ancora, né il livello ingrediente generico esiste (S4, TBD dichiarato).
COLLECTED_FIELDS: frozenset[str] = frozenset(
    {
        "kcal",
        "protein",
        "carbs",
        "sugars",
        "fat",
        "saturated_fat",
        "fiber",
        "salt",
        "vitamin_c",
        "calcium",
        "iron",
        "potassium",
    }
)

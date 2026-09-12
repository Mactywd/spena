from pathlib import Path

import pytest

from app.services.recipe_import.giallozafferano import (
    TERM_KEY_MAX_CHARS,
    UnparsablePage,
    parse_recipe,
    term_key,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "giallozafferano"


def fixture(name: str) -> str:
    return (FIXTURES / f"{name}.html").read_text(encoding="utf-8")


def test_legge_i_campi_dal_blocco_strutturato():
    recipe = parse_recipe(fixture("semplice"))

    assert recipe.title == "Pasta con crema di Parmigiano e speck"
    assert recipe.description.startswith("Un primo piatto cremoso")
    assert recipe.servings == 4
    assert recipe.category == "Primi piatti"
    assert recipe.prep_minutes == 10
    assert recipe.cook_minutes == 15
    assert recipe.image_url.endswith("pasta-crema-parmigiano.jpg")


def test_i_rimandi_alle_foto_non_arrivano_nel_procedimento():
    recipe = parse_recipe(fixture("semplice"))

    assert " 1 ." not in recipe.instructions
    assert recipe.instructions.startswith("Riducete lo speck a striscioline di circa 1 cm.")
    assert recipe.instructions.count("\n\n") == 2


def test_gli_ingredienti_arrivano_con_chiave_nome_e_dose():
    recipe = parse_recipe(fixture("semplice"))

    assert [i.key for i in recipe.ingredients] == [
        "ricette-con-i-Rigatoni",
        "ricette-con-lo-Speck",
        "ricette-con-Pepe-nero",
    ]
    assert [i.name for i in recipe.ingredients] == ["Rigatoni", "Speck", "Pepe nero"]
    assert [i.quantity_text for i in recipe.ingredients] == ["320 g", "a fette 80 g", "q.b."]


def test_i_valori_nutrizionali_si_conservano_alla_lettera():
    """Nessuno li usa oggi: sono ciò che permette alla fase 3 di non riscaricare."""
    recipe = parse_recipe(fixture("semplice"))

    assert recipe.nutrition["calories"] == "464,4 kcal"


def test_i_gruppi_non_perdono_righe_e_le_entita_si_decodificano():
    recipe = parse_recipe(fixture("gruppi"))

    assert len(recipe.ingredients) == 6
    scorza = next(i for i in recipe.ingredients if i.name == "Scorza di limone")
    assert scorza.quantity_text == "non trattato ½"


def test_lo_stesso_termine_puo_comparire_due_volte():
    """Il parser non collassa niente: è la materializzazione a farlo, perché è lei
    a conoscere l'ingrediente su cui le due righe finiscono."""
    recipe = parse_recipe(fixture("gruppi"))

    chiavi = [i.key for i in recipe.ingredients]
    assert chiavi.count("ricette-con-Zucchero-a-velo") == 2


def test_una_riga_senza_link_ha_comunque_una_chiave():
    recipe = parse_recipe(fixture("gruppi"))

    amido = next(i for i in recipe.ingredients if i.name == "Amido di riso")
    assert amido.key == "testo:amido di riso"
    assert amido.quantity_text == "20 g"


def test_le_porzioni_scritte_a_parole_si_leggono():
    assert parse_recipe(fixture("gruppi")).servings == 10


def test_un_link_senza_niente_dentro_ricade_sul_nome():
    """`<a href="/">` e `<a href="">` sono link senza niente dentro: `strip("/")`
    li riduce a stringa vuota, che `sync_terms` scarta e che nessuna decisione può
    mai sbloccare — una pagina che resta per sempre in attesa di un termine che
    non può esistere, invisibile perché il conteggio in attesa non torna a zero.
    Devono ricadere sul nome esattamente come una riga senza link."""
    assert term_key("/", "Sale fino") == "testo:sale fino"
    assert term_key("", "Sale fino") == "testo:sale fino"
    assert term_key(None, "Sale fino") == "testo:sale fino"


def test_un_href_piu_lungo_della_colonna_si_tronca():
    """`term_key` è `String(200)` in `recipe_import.py`: un href più lungo
    abortirebbe il giro con un IntegrityError invece di limitarsi a non essere
    granulare come potrebbe."""
    href = "/" + ("ricette-con-un-nome-lunghissimo-" * 10)
    assert len(href.strip("/")) > TERM_KEY_MAX_CHARS

    key = term_key(href, "Qualcosa")

    assert len(key) == TERM_KEY_MAX_CHARS
    assert key == href.strip("/")[:TERM_KEY_MAX_CHARS]


def test_il_blocco_dentro_una_lista_si_trova():
    """Il JSON-LD della fonte a volte è un oggetto, a volte una lista."""
    assert parse_recipe(fixture("gruppi")).title == "Torta della nonna"


def test_i_passaggi_a_oggetti_howtostep_si_leggono():
    instructions = parse_recipe(fixture("gruppi")).instructions

    assert instructions.startswith("Lavorate la farina con il burro freddo.")
    assert "Stendete la frolla nello stampo." in instructions


def test_una_pagina_senza_blocco_strutturato_dice_perche():
    with pytest.raises(UnparsablePage) as errore:
        parse_recipe(fixture("senza-jsonld"))

    assert "schema.org" in errore.value.reason


def test_una_pagina_senza_ingredienti_dice_perche():
    html = fixture("semplice").replace('class="gz-ingredient"', 'class="niente"')

    with pytest.raises(UnparsablePage) as errore:
        parse_recipe(html)

    assert "ingredient" in errore.value.reason


def test_il_payload_e_serializzabile_in_json():
    import json

    payload = parse_recipe(fixture("semplice")).as_payload()

    assert json.loads(json.dumps(payload))["ingredients"][0]["key"] == "ricette-con-i-Rigatoni"

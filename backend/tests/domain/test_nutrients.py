from app.domain.nutrients import COLLECTED_FIELDS, NUTRIENT_FIELDS
from app.services.openfoodfacts import _NUTRIENT_MAP


def test_every_collected_field_is_in_the_vocabulary():
    for key in COLLECTED_FIELDS:
        assert key in NUTRIENT_FIELDS


def test_every_off_mapped_key_is_in_the_vocabulary():
    """`_NUTRIENT_MAP` non deve mai scrivere una chiave che il vocabolario non
    conosce: sarebbe un dato senza unità né etichetta da nessuna parte."""
    for our_key in _NUTRIENT_MAP.values():
        assert our_key in NUTRIENT_FIELDS


def test_every_off_mapped_key_is_marked_collected():
    for our_key in _NUTRIENT_MAP.values():
        assert our_key in COLLECTED_FIELDS


def test_every_field_has_a_label_and_a_unit_the_import_can_convert_to():
    """La raccolta da Open Food Facts converte dai grammi con un fattore per
    unità: un'unità nuova senza fattore farebbe cadere ogni scansione."""
    for key, field in NUTRIENT_FIELDS.items():
        assert field.label, key
        assert field.unit in {"kcal", "g", "mg", "µg"}, key


def test_vnr_values_match_allegato_xiii():
    # Regolamento UE 1169/2011, Allegato XIII, parti A e B
    assert NUTRIENT_FIELDS["kcal"].vnr == 2000
    assert NUTRIENT_FIELDS["salt"].vnr == 6
    assert NUTRIENT_FIELDS["vitamin_c"].vnr == 80
    assert NUTRIENT_FIELDS["calcium"].vnr == 800
    assert NUTRIENT_FIELDS["iron"].vnr == 14
    assert NUTRIENT_FIELDS["potassium"].vnr == 2000


def test_fiber_has_no_normed_vnr():
    """Il regolamento non fissa un VNR per le fibre: None è la verità, non un
    buco da riempire con un numero inventato."""
    assert NUTRIENT_FIELDS["fiber"].vnr is None


def test_vocabulary_holds_fields_not_collected_yet():
    """Il livello ingrediente generico non esiste ancora, ma il vocabolario
    già nomina campi che oggi nessuna fonte riempie (S4, fuori scopo)."""
    assert "vitamin_a" in NUTRIENT_FIELDS
    assert "vitamin_a" not in COLLECTED_FIELDS

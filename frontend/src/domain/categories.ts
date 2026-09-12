/** Le categorie dell'anagrafica, nell'ordine in cui si offrono.
 *
 * Sono i valori di `IngredientCategory` nel backend, ed è l'unico posto del
 * frontend che li nomina. Un valore inventato qui non sarebbe un errore visibile:
 * la creazione dell'ingrediente tornerebbe 422 dal backend, su una schermata che
 * fino a quel momento sembrava funzionare. `backend/tests/test_frontend_categories.py`
 * confronta i due elenchi per impedirlo.
 */
export const INGREDIENT_CATEGORIES = [
  "verdura",
  "frutta",
  "carne",
  "pesce",
  "latticini",
  "cereali",
  "legumi",
  "condimenti",
  "spezie",
  "bevande",
  "dolci",
  "altro",
] as const;

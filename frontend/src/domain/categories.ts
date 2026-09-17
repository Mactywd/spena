/** I reparti dell'anagrafica, nell'ordine in cui si offrono.
 *
 * Sono i valori di `IngredientCategory` nel backend, ed è l'unico posto del
 * frontend che li nomina. Un valore inventato qui non sarebbe un errore visibile:
 * la creazione dell'ingrediente tornerebbe 422 dal backend, su una schermata che
 * fino a quel momento sembrava funzionare. `backend/tests/test_frontend_categories.py`
 * confronta i due elenchi per impedirlo.
 *
 * Sono **due** e non uno perché i reparti non alimentari non vanno offerti
 * dappertutto: chi scrive una ricetta non deve poter mettere un ingrediente in
 * «igiene», perché la guardia del backend rifiuterebbe il salvataggio un istante
 * dopo. Quale metà usare lo decide lo schermo, non questo file.
 */
export const FOOD_CATEGORIES = [
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

export const NON_FOOD_CATEGORIES = ["casa", "igiene"] as const;

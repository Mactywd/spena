import { useQuery } from "@tanstack/react-query";
import type { Ingredient } from "../../domain/types";
import { useDebounced } from "../../hooks/useDebounced";
import { matchNewName } from "./api";

// la stessa attesa del selettore degli ingredienti: una domanda per nome scritto, non
// una per tasto
const DEBOUNCE_MS = 180;

/** Il perché sotto «Aggiungi alla ricetta» quando il nome è un non alimentare. */
export const NON_FOOD_NAME_PROBLEM = "Cambia il nome: questo è un non alimentare.";

/** Se il nome scritto nel passo del nome di R12 porta, salvando, a un non alimentare
 * dell'anagrafica: quell'ingrediente, o `null` (piano 20). `null` come argomento: il
 * passo è chiuso, e non si chiede niente.
 *
 * Lo dice il server, con la stessa funzione del salvataggio: il `kind` arriva, non si
 * calcola. La risposta vale solo per il nome scritto adesso — mentre si scrive, quella di
 * prima non dice niente — e `null` anche quando il server non risponde o non ha ancora
 * risposto: il passo non si ferma mai per una domanda senza risposta, e l'ultima linea
 * resta il 422 del salvataggio. `refetchOnWindowFocus` in esplicito: chi torna dalla
 * scheda dell'Anagrafica dopo averla corretta deve vedere la risposta nuova. */
export function useNonFoodName(name: string | null): Ingredient | null {
  const typed = (name ?? "").trim();
  const settled = useDebounced(typed, DEBOUNCE_MS);
  const { data } = useQuery({
    queryKey: ["ingredient-match", settled.toLowerCase()],
    queryFn: () => matchNewName(settled),
    enabled: name !== null && settled !== "",
    refetchOnWindowFocus: true,
  });
  if (name === null || settled === "" || settled !== typed) return null;
  const ingredient = data?.ingredient;
  return ingredient?.kind === "non_food" ? ingredient : null;
}

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { searchIngredients } from "../features/shopping-list/api";
import { useDebounced } from "../hooks/useDebounced";
import type { Ingredient } from "../domain/types";

const DEBOUNCE_MS = 180;

/** Scegliere un ingrediente dall'anagrafica, con i suggerimenti del backend.
 *
 * Unico per l'app: lo usa lo schermo della stesura AI per agganciare un
 * ingrediente che la bozza non ha trovato, e la dispensa per far entrare a mano
 * qualcosa che non era in lista. Stava dentro AiDraftScreen, e il secondo schermo
 * che ne aveva bisogno è il momento di estrarlo: due copie della stessa ricerca si
 * scollano, e la prima a scollarsi è sempre la regola che l'errore deve passare
 * dalla QueryCache.
 *
 * La ricerca passa da `useQuery`: un 401 deve arrivare alla cache che App.tsx
 * aggancia all'accesso, non morire in un `.catch` locale.
 */
export function IngredientPicker({
  label,
  failureNote,
  onPick,
  disabled = false,
}: {
  /** Etichetta visibile e nome accessibile: dice a cosa serve *qui*. */
  label: string;
  /** Cosa resta possibile se la ricerca non risponde: ogni schermo ha la sua via
   * d'uscita, e nominarla è quel che la distingue da un vicolo cieco. */
  failureNote: string;
  onPick: (ingredient: Ingredient) => void;
  /** Mentre la scrittura nata dalla scelta precedente è ancora in volo. */
  disabled?: boolean;
}) {
  const [term, setTerm] = useState("");
  const debounced = useDebounced(term, DEBOUNCE_MS).trim();
  // sotto 2 caratteri non vale la pena interrogare il backend, come in AddItemField
  const ready = debounced.length >= 2;

  const { data: found = [], isError } = useQuery({
    queryKey: ["ingredients", debounced],
    queryFn: () => searchIngredients(debounced),
    enabled: ready,
  });

  // sul testo corrente, non sul termine ritardato: svuotando il campo l'elenco
  // deve sparire subito, non dopo l'attesa
  const showOptions = term.trim().length >= 2;

  return (
    <div className="flex flex-col gap-2 pt-2">
      <label className="text-sm">
        {label}
        <input
          aria-label={label}
          value={term}
          onChange={(e) => setTerm(e.target.value)}
          placeholder="Cerca in anagrafica"
          disabled={disabled}
          className="mt-1 w-full rounded border px-3 py-3 text-base disabled:opacity-50"
        />
      </label>

      {showOptions && found.length > 0 && (
        <ul role="listbox" className="overflow-hidden rounded-lg border border-neutral-200">
          {found.map((ingredient) => (
            <li key={ingredient.id}>
              <button
                type="button"
                role="option"
                aria-selected={false}
                disabled={disabled}
                onClick={() => {
                  onPick(ingredient);
                  setTerm("");
                }}
                className="min-h-11 w-full px-3 py-3 text-left text-sm disabled:opacity-50"
              >
                {ingredient.display_name}
                <span className="ml-2 text-xs text-neutral-400">{ingredient.category}</span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {/* la ricerca è un aiuto, non un pedaggio: il guasto va detto insieme a
          quello che resta possibile */}
      {isError && (
        <p role="alert" className="text-sm text-amber-700">
          La ricerca degli ingredienti non risponde. {failureNote}
        </p>
      )}
    </div>
  );
}

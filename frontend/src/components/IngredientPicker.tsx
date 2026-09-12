import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { searchIngredients } from "../features/shopping-list/api";
import { useDebounced } from "../hooks/useDebounced";
import { OptionList } from "./ui/OptionList";
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
  accessibleLabel,
  failureNote,
  onPick,
  disabled = false,
}: {
  /** Etichetta visibile: dice a cosa serve *qui*. */
  label: string;
  /** Nome accessibile, quando deve dire più della scritta in vista — per esempio
   * quale termine sta per agganciare, in un elenco dove la scritta in vista si
   * ripete identica scheda per scheda. Di norma coincide con `label`. */
  accessibleLabel?: string;
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
    <div className="flex flex-col gap-2">
      <label className="text-sm font-medium text-ink-soft">
        {label}
        <input
          aria-label={accessibleLabel ?? label}
          value={term}
          onChange={(e) => setTerm(e.target.value)}
          placeholder="Cerca in anagrafica"
          disabled={disabled}
          className="mt-1.5 disabled:opacity-50"
        />
      </label>

      {showOptions && found.length > 0 && (
        <OptionList
          options={found}
          disabled={disabled}
          onPick={(ingredient) => {
            onPick(ingredient);
            setTerm("");
          }}
        />
      )}

      {/* la ricerca è un aiuto, non un pedaggio: il guasto va detto insieme a
          quello che resta possibile. L'ambra è il colore che nell'app vuol dire
          «funziona, ma non del tutto» — lo stesso di «quasi finito» */}
      {isError && (
        <p role="alert" className="text-sm text-low">
          La ricerca degli ingredienti non risponde. {failureNote}
        </p>
      )}
    </div>
  );
}

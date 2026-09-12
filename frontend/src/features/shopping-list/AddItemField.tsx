import { useState } from "react";
import type { FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { searchIngredients } from "./api";
import { useDebounced } from "../../hooks/useDebounced";

const DEBOUNCE_MS = 180;

export function AddItemField({
  onAdd,
}: {
  onAdd: (rawText: string, ingredientId?: string) => Promise<unknown> | void;
}) {
  const [text, setText] = useState("");
  const [failed, setFailed] = useState(false);
  const term = useDebounced(text, DEBOUNCE_MS).trim();
  // sotto 2 caratteri non vale la pena interrogare il backend: il testo resta libero
  const enabled = term.length >= 2;

  // La ricerca passa da `useQuery`, come in RecipeBookScreen e in IngredientPicker.
  // Due cose che un `.catch` locale non dà. La sicurezza sull'ordine diventa
  // strutturale: il termine sta nella chiave, quindi una risposta superata atterra
  // sotto la propria chiave e non può sovrascrivere suggerimenti più recenti. E un
  // 401 arriva alla QueryCache che App.tsx aggancia al ritorno all'accesso: prima
  // moriva qui dentro, e a sessione scaduta il campo smetteva di suggerire senza
  // dire perché — gli altri due consumatori della stessa ricerca erano già stati
  // corretti, questo era il terzo.
  const { data: suggestions = [], isError } = useQuery({
    queryKey: ["ingredients", term],
    queryFn: () => searchIngredients(term),
    enabled,
  });

  // sul testo corrente, non sul termine ritardato: svuotando il campo i
  // suggerimenti devono sparire subito, non dopo l'attesa
  const showSuggestions = text.trim().length >= 2;

  async function add(rawText: string, ingredientId?: string) {
    setFailed(false);
    try {
      await onAdd(rawText, ingredientId);
    } catch {
      // il testo resta nel campo. Svuotarlo prima di sapere com'è andata perde
      // quello che l'utente ha scritto, che è il peggiore dei vicoli ciechi
      setFailed(true);
      return;
    }
    setText("");
  }

  function submitFreeText(event: FormEvent) {
    event.preventDefault();
    const trimmed = text.trim();
    if (!trimmed) return;
    // niente corrispondenza non è un errore: la voce entra grezza
    void add(trimmed, undefined);
  }

  return (
    <form onSubmit={submitFreeText} className="sticky top-0 bg-white p-4">
      <label htmlFor="add-item" className="sr-only">Aggiungi alla lista</label>
      <div className="flex gap-2">
        <input
          id="add-item"
          aria-label="Aggiungi alla lista"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Cosa serve?"
          className="min-w-0 flex-1 rounded-lg border border-neutral-300 px-3 py-3 text-base"
        />
        {/* un bersaglio visibile: da telefono il tasto invio della tastiera non si
            vede, e il testo libero è il percorso che non deve mai essere nascosto */}
        <button
          type="submit"
          disabled={text.trim().length === 0}
          className="min-h-11 rounded-lg bg-emerald-700 px-4 py-3 text-white disabled:opacity-40"
        >
          Aggiungi
        </button>
      </div>
      {failed && (
        <p role="alert" className="mt-2 text-sm text-red-600">
          Non sono riuscito ad aggiungere la voce. Il testo è ancora qui: riprova.
        </p>
      )}
      {/* una ricerca che non risponde non deve bloccare la scrittura, e nemmeno
          restare muta: il testo libero passa comunque, e va detto che passerà
          senza ingrediente abbinato. `status` e non `alert`: è una rinuncia, non
          un guasto da interrompere quel che si sta scrivendo */}
      {showSuggestions && isError && (
        <p role="status" className="mt-2 text-sm text-amber-700">
          L'autocomplete non risponde. Puoi aggiungere la voce così com'è: l'ingrediente
          si abbina dopo.
        </p>
      )}
      {showSuggestions && suggestions.length > 0 && (
        <ul role="listbox" className="mt-1 overflow-hidden rounded-lg border border-neutral-200">
          {suggestions.map((ingredient) => (
            <li key={ingredient.id}>
              <button
                type="button"
                role="option"
                aria-selected={false}
                onClick={() => void add(ingredient.name, ingredient.id)}
                className="min-h-11 w-full px-3 py-3 text-left"
              >
                {ingredient.display_name}
                <span className="ml-2 text-xs text-neutral-400">{ingredient.category}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </form>
  );
}

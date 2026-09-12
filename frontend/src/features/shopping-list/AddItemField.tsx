import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { searchIngredients } from "./api";
import type { Ingredient } from "../../domain/types";

const DEBOUNCE_MS = 180;

export function AddItemField({
  onAdd,
}: {
  onAdd: (rawText: string, ingredientId?: string) => Promise<unknown> | void;
}) {
  const [text, setText] = useState("");
  const [suggestions, setSuggestions] = useState<Ingredient[]>([]);
  const [failed, setFailed] = useState(false);
  // sotto 2 caratteri non vale la pena interrogare il backend: il testo resta libero
  const showSuggestions = text.trim().length >= 2;

  useEffect(() => {
    if (!showSuggestions) return;
    // `superseded` è la guardia contro le risposte fuori ordine: due ricerche possono
    // essere in volo insieme e la più lenta può essere la più vecchia. Senza questo,
    // i suggerimenti per "po" arrivati in ritardo sovrascrivono quelli per "pomo" e
    // l'utente sceglie l'ingrediente sbagliato senza accorgersi di nulla.
    let superseded = false;
    const timer = setTimeout(() => {
      searchIngredients(text)
        .then((found) => {
          if (!superseded) setSuggestions(found);
        })
        // una ricerca che non risponde non deve bloccare la scrittura: il campo
        // resta usabile e il testo libero passa comunque
        .catch(() => {
          if (!superseded) setSuggestions([]);
        });
    }, DEBOUNCE_MS);
    return () => {
      superseded = true;
      clearTimeout(timer);
    };
  }, [text, showSuggestions]);

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
    setSuggestions([]);
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
          className="rounded-lg bg-emerald-700 px-4 py-3 text-white disabled:opacity-40"
        >
          Aggiungi
        </button>
      </div>
      {failed && (
        <p role="alert" className="mt-2 text-sm text-red-600">
          Non sono riuscito ad aggiungere la voce. Il testo è ancora qui: riprova.
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
                className="w-full px-3 py-3 text-left"
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

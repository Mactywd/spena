import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { searchIngredients } from "./api";
import type { Ingredient } from "../../domain/types";

const DEBOUNCE_MS = 180;

export function AddItemField({
  onAdd,
}: {
  onAdd: (rawText: string, ingredientId?: string) => void;
}) {
  const [text, setText] = useState("");
  const [suggestions, setSuggestions] = useState<Ingredient[]>([]);
  // sotto 2 caratteri non vale la pena interrogare il backend: il testo resta libero
  const showSuggestions = text.trim().length >= 2;

  useEffect(() => {
    if (!showSuggestions) return;
    const timer = setTimeout(() => {
      searchIngredients(text).then(setSuggestions).catch(() => setSuggestions([]));
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [text, showSuggestions]);

  function submitFreeText(event: FormEvent) {
    event.preventDefault();
    const trimmed = text.trim();
    if (!trimmed) return;
    // niente corrispondenza non è un errore: la voce entra grezza
    onAdd(trimmed, undefined);
    setText("");
    setSuggestions([]);
  }

  function choose(ingredient: Ingredient) {
    onAdd(ingredient.name, ingredient.id);
    setText("");
    setSuggestions([]);
  }

  return (
    <form onSubmit={submitFreeText} className="sticky top-0 bg-white p-4">
      <label htmlFor="add-item" className="sr-only">Aggiungi alla lista</label>
      <input
        id="add-item"
        aria-label="Aggiungi alla lista"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Cosa serve?"
        className="w-full rounded-lg border border-neutral-300 px-3 py-3 text-base"
      />
      {showSuggestions && suggestions.length > 0 && (
        <ul role="listbox" className="mt-1 overflow-hidden rounded-lg border border-neutral-200">
          {suggestions.map((ingredient) => (
            <li key={ingredient.id}>
              <button
                type="button"
                role="option"
                aria-selected={false}
                onClick={() => choose(ingredient)}
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

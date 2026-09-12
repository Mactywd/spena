import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { RecipeCard } from "./RecipeCard";
import { searchRecipes } from "./api";

const DEBOUNCE_MS = 180;

/** Ritarda il valore, così la ricerca non parte a ogni tasto premuto. */
function useDebounced(value: string, ms: number): string {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), ms);
    return () => clearTimeout(timer);
  }, [value, ms]);
  return settled;
}

export function RecipeBookScreen() {
  const [query, setQuery] = useState("");
  const [onlyCookable, setOnlyCookable] = useState(false);
  const debouncedQuery = useDebounced(query, DEBOUNCE_MS);

  // Il termine sta dentro la chiave, e questo fa due cose che una ricerca scritta
  // a mano non fa. La sicurezza sull'ordine diventa strutturale: una risposta
  // superata atterra sotto la propria chiave e non può sovrascrivere risultati più
  // recenti, senza bisogno di guardarla. E l'errore passa dalla QueryCache che
  // App.tsx aggancia al 401: una sessione scaduta riporta all'accesso, invece di
  // diventare un "ricerca fallita" permanente su uno schermo che non funzionerà
  // mai più. La prima versione di questo schermo sbagliava esattamente lì.
  const { data: recipes = [], isLoading, isError } = useQuery({
    queryKey: ["recipes", debouncedQuery, onlyCookable],
    queryFn: () => searchRecipes(debouncedQuery, onlyCookable),
  });

  return (
    <div className="p-4">
      <div className="flex items-baseline justify-between pb-3">
        <h1 className="text-xl font-semibold">Ricette</h1>
        <Link to="/ricette/nuova-ai" className="text-sm text-emerald-700">
          Scrivi con l'AI
        </Link>
      </div>

      <label htmlFor="recipe-search" className="sr-only">Cerca nel ricettario</label>
      <input
        id="recipe-search"
        aria-label="Cerca nel ricettario"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Cerca un piatto o un ingrediente"
        className="w-full rounded-lg border border-neutral-300 px-3 py-3 text-base"
      />

      <label className="mt-3 flex items-center gap-2 text-sm text-neutral-600">
        <input
          type="checkbox"
          aria-label="Solo quelle che posso cucinare"
          checked={onlyCookable}
          onChange={(e) => setOnlyCookable(e.target.checked)}
          className="size-4"
        />
        Solo quelle che posso cucinare
      </label>

      {isLoading && <p className="pt-4 text-neutral-500">Cerco…</p>}

      {!isLoading && isError && (
        <p role="alert" className="pt-4 text-sm text-red-600">
          Non sono riuscito a cercare nel ricettario. Riprova, o scrivine una con l'AI.
        </p>
      )}

      {!isLoading && !isError && recipes.length === 0 && (
        <p className="pt-4 text-neutral-500">Nessuna ricetta. Provane una scritta con l'AI.</p>
      )}

      {!isLoading && !isError && recipes.length > 0 && (
        <ul className="divide-y divide-neutral-100 pt-2">
          {recipes.map((recipe) => (
            <RecipeCard key={recipe.id} recipe={recipe} />
          ))}
        </ul>
      )}
    </div>
  );
}

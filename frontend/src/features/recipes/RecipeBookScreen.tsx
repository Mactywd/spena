import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { RecipeCard } from "./RecipeCard";
import { searchRecipes } from "./api";
import type { RecipeSummary } from "../../domain/types";

const DEBOUNCE_MS = 180;

export function RecipeBookScreen() {
  const [query, setQuery] = useState("");
  const [onlyCookable, setOnlyCookable] = useState(false);
  const [recipes, setRecipes] = useState<RecipeSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isError, setIsError] = useState(false);

  useEffect(() => {
    // `superseded` è la guardia contro le risposte fuori ordine: digitare in
    // fretta, o toccare il filtro subito dopo, può lasciare in volo una ricerca
    // vecchia insieme a una nuova, e la più lenta può arrivare dopo. Senza
    // questo una ricerca superata che risponde in ritardo sovrascriverebbe
    // risultati già più recenti sullo schermo — lo stesso difetto costato un
    // MAJOR nel campo di aggiunta della lista della spesa (AddItemField).
    let superseded = false;
    const timer = setTimeout(() => {
      setIsLoading(true);
      searchRecipes(query, onlyCookable)
        .then((found) => {
          if (superseded) return;
          setRecipes(found);
          setIsLoading(false);
          setIsError(false);
        })
        // una ricerca rotta non è un ricettario vuoto: dirlo sarebbe una bugia,
        // e qui la differenza conta più che altrove perché una ricerca
        // semantica senza risultati ha lo stesso aspetto di una ricerca rotta
        .catch(() => {
          if (superseded) return;
          setIsLoading(false);
          setIsError(true);
        });
    }, DEBOUNCE_MS);
    return () => {
      superseded = true;
      clearTimeout(timer);
    };
  }, [query, onlyCookable]);

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

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { RecipeCard } from "./RecipeCard";
import { fetchSearchMode, searchRecipes } from "./api";
import { useDebounced } from "../../hooks/useDebounced";

const DEBOUNCE_MS = 180;

/** Perché non c'è niente da mostrare: parole cercate e filtro, quattro casi.
 *
 * «Nessuna ricetta» è un verdetto sul ricettario, e il ricettario del seme ne ha 26:
 * con la soglia semantica di `recipe_search.py` una risposta vuota è diventata
 * raggiungibile per la prima volta, e quasi sempre riguarda le parole cercate o il
 * filtro, non il ricettario. È lo stesso errore che b6ed1d9 ha corretto nel pannello
 * del catalogo («con queste parole», non «in catalogo»), dall'altro lato dell'app.
 */
function emptyMessage(query: string, onlyCookable: boolean): string {
  const searched = query.trim() !== "";
  if (searched && onlyCookable) {
    return (
      "Nessuna ricetta con queste parole fra quelle che puoi cucinare adesso: " +
      "togli il filtro, o prova con altre parole."
    );
  }
  if (searched) {
    return "Nessuna ricetta con queste parole: provane altre, o scrivine una con l'AI.";
  }
  if (onlyCookable) {
    return (
      "Niente che puoi cucinare con quel che hai in dispensa: togli il filtro per " +
      "vedere tutto il ricettario."
    );
  }
  return "Nessuna ricetta. Provane una scritta con l'AI.";
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

  // Spec §11: quando il modello di embedding non si carica la ricerca resta solo
  // testuale, e va detto con un avviso discreto. Fuori dalla chiave ["recipes"],
  // che il salvataggio di una ricetta invalida: questo non cambia salvando una
  // ricetta, cambia solo quando il backend riparte. Se la rotta non risponde non si
  // mostra niente: un avviso rotto su una cosa che forse funziona è peggio del
  // silenzio.
  const { data: searchMode } = useQuery({
    queryKey: ["search-mode"],
    queryFn: fetchSearchMode,
    staleTime: Infinity,
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

      {/* una constatazione, non un guasto: niente `role`, niente colore d'allarme.
          `=== false` e non `!searchMode?.semantic`, perché "non lo so ancora" e
          "non risponde" non sono "è degradata" */}
      {searchMode?.semantic === false && (
        <p className="pt-2 text-xs text-neutral-400">
          Ricerca solo testuale: trova le parole che scrivi, non i piatti simili.
        </p>
      )}

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
        <p className="pt-4 text-neutral-500">
          {emptyMessage(debouncedQuery, onlyCookable)}
        </p>
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

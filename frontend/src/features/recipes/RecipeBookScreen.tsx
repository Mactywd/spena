import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { RecipeCard } from "./RecipeCard";
import { fetchCategories, fetchSearchMode, searchRecipes } from "./api";
import { fetchImportStatus } from "../recipe-import/api";
import { useDebounced } from "../../hooks/useDebounced";
import { Alert } from "../../components/ui/Alert";
import { Screen } from "../../components/ui/Screen";

const DEBOUNCE_MS = 180;

/** Perché non c'è niente da mostrare: parole cercate e filtro, quattro casi.
 *
 * «Nessuna ricetta» è un verdetto sul ricettario, e il ricettario del seme ne ha 26:
 * con la soglia semantica di `recipe_search.py` una risposta vuota è diventata
 * raggiungibile per la prima volta, e quasi sempre riguarda le parole cercate o il
 * filtro, non il ricettario. È lo stesso errore che b6ed1d9 ha corretto nel pannello
 * del catalogo («con queste parole», non «in catalogo»), dall'altro lato dell'app.
 */
function emptyMessage(query: string, onlyCookable: boolean, category: string): string {
  const searched = query.trim() !== "";
  if (category) {
    const conParole = searched ? " con queste parole" : "";
    const cucinabili = onlyCookable ? " fra quelle che puoi cucinare adesso" : "";
    return (
      `Nessuna ricetta in «${category}»${conParole}${cucinabili}: ` +
      "scegli «Tutte» per vedere il resto del ricettario."
    );
  }
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
  const [category, setCategory] = useState("");
  const debouncedQuery = useDebounced(query, DEBOUNCE_MS);

  // Il termine sta dentro la chiave, e questo fa due cose che una ricerca scritta
  // a mano non fa. La sicurezza sull'ordine diventa strutturale: una risposta
  // superata atterra sotto la propria chiave e non può sovrascrivere risultati più
  // recenti, senza bisogno di guardarla. E l'errore passa dalla QueryCache che
  // App.tsx aggancia al 401: una sessione scaduta riporta all'accesso, invece di
  // diventare un "ricerca fallita" permanente su uno schermo che non funzionerà
  // mai più. La prima versione di questo schermo sbagliava esattamente lì.
  const { data: recipes = [], isLoading, isError } = useQuery({
    queryKey: ["recipes", debouncedQuery, onlyCookable, category],
    queryFn: () => searchRecipes(debouncedQuery, onlyCookable, category),
  });

  // le categorie presenti, non tutte quelle possibili: un filtro che offre voci
  // vuote porta a una schermata vuota
  const { data: categories = [] } = useQuery({
    queryKey: ["recipe-categories"],
    queryFn: fetchCategories,
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

  // Fuori dalla chiave ["recipes"]: questa non cambia cercando, cambia quando si
  // decide un termine o si scarica un lotto. Se la rotta non risponde non si mostra
  // niente: una riga rotta su una cosa che forse funziona è peggio del silenzio.
  const { data: importStatus } = useQuery({
    queryKey: ["import-status"],
    queryFn: fetchImportStatus,
  });

  return (
    <Screen
      title="Ricette"
      action={
        <Link
          to="/ricette/nuova-ai"
          className="min-h-11 shrink-0 content-center text-sm font-medium text-brand"
        >
          Scrivi con l'AI
        </Link>
      }
    >
      {importStatus && importStatus.pending_terms > 0 && (
        <Link
          to="/ricette/importa"
          className="mb-3 flex min-h-11 items-center justify-between rounded-card bg-low-tint px-3.5 py-3 text-sm text-low"
        >
          <span>
            {importStatus.pending_terms === 1
              ? "1 ingrediente da abbinare"
              : `${importStatus.pending_terms} ingredienti da abbinare`}
            ,{" "}
            {importStatus.pending_recipes === 1
              ? "1 ricetta in attesa"
              : `${importStatus.pending_recipes} ricette in attesa`}
          </span>
          <span aria-hidden="true">›</span>
        </Link>
      )}

      <label htmlFor="recipe-search" className="sr-only">Cerca nel ricettario</label>
      <input
        id="recipe-search"
        aria-label="Cerca nel ricettario"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Cerca un piatto o un ingrediente"
      />

      {/* una constatazione, non un guasto: niente `role`, niente colore d'allarme.
          `=== false` e non `!searchMode?.semantic`, perché "non lo so ancora" e
          "non risponde" non sono "è degradata" */}
      {searchMode?.semantic === false && (
        <p className="pt-2 text-xs text-ink-faint">
          Ricerca solo testuale: trova le parole che scrivi, non i piatti simili.
        </p>
      )}

      <label className="flex min-h-11 items-center gap-2.5 text-sm text-ink-soft">
        <input
          type="checkbox"
          aria-label="Solo quelle che posso cucinare"
          checked={onlyCookable}
          onChange={(e) => setOnlyCookable(e.target.checked)}
          className="size-5"
        />
        Solo quelle che posso cucinare
      </label>

      {categories.length > 0 && (
        <label className="text-sm font-medium text-ink-soft">
          Categoria
          <select
            aria-label="Categoria"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="mt-1.5"
          >
            <option value="">Tutte</option>
            {categories.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
      )}

      {isLoading && <p className="pt-4 text-ink-soft">Cerco…</p>}

      {!isLoading && isError && (
        <Alert className="pt-4">
          Non sono riuscito a cercare nel ricettario. Riprova, o scrivine una con l'AI.
        </Alert>
      )}

      {!isLoading && !isError && recipes.length === 0 && (
        <p className="pt-4 text-ink-soft">{emptyMessage(debouncedQuery, onlyCookable, category)}</p>
      )}

      {!isLoading && !isError && recipes.length > 0 && (
        <ul className="flex flex-col gap-2 pt-2">
          {recipes.map((recipe) => (
            <RecipeCard key={recipe.id} recipe={recipe} />
          ))}
        </ul>
      )}
    </Screen>
  );
}

import { useEffect, useId, useState } from "react";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { RecipeRow } from "./RecipeRow";
import { RecipeFiltersPanel } from "./RecipeFiltersPanel";
import { MissingBudgetFilter } from "./MissingBudgetFilter";
import { MAX_BUDGET } from "./missingBudget";
import { fetchCategories, fetchSearchMode, nextPageOffset, searchRecipes } from "./api";
import {
  activeFilterCount,
  filtersButtonName,
  loadFilters,
  resultsLabel,
  saveFilters,
  type RecipeFilters,
} from "./recipeFilters";
import { fetchImportStatus } from "../recipe-import/api";
import { useDebounced } from "../../hooks/useDebounced";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { buttonClasses } from "../../components/ui/buttonClasses";
import { EmptyState } from "../../components/ui/EmptyState";
import { ErrorState } from "../../components/ui/ErrorState";
import { Screen } from "../../components/ui/Screen";
import { SectionEntryCard } from "../../components/ui/SectionEntryCard";
import {
  IconAdjustmentsHorizontal,
  IconClearAll,
  IconPencilPlus,
  IconSearch,
} from "../../components/ui/icons";
import type { Ingredient } from "../../domain/types";

const DEBOUNCE_MS = 180;

/** «A», «B» e «C»: la virgola fra i primi e la «e» prima dell'ultimo, come si
 * scrive un elenco. Con «e» dappertutto tre ingredienti si leggono come una
 * filastrocca, e questo messaggio è già lungo di suo. */
function elenco(names: string[]): string {
  const quoted = names.map((name) => `«${name}»`);
  if (quoted.length <= 1) return quoted.join("");
  return `${quoted.slice(0, -1).join(", ")} e ${quoted[quoted.length - 1]}`;
}

/** Come si nomina la soglia dentro le frasi degli altri rami.
 *
 * Un posto solo: quattro rami che se la scrivono a mano si scollano al primo cambio
 * di parole, e il primo a scollarsi sarebbe quello che si legge meno spesso.
 */
function frammentoSoglia(maxMissing: number | null): string {
  if (maxMissing === null) return "";
  if (maxMissing === 0) return " fra quelle che puoi cucinare adesso";
  if (maxMissing === 1) return " fra quelle a cui manca al massimo 1 ingrediente";
  return ` fra quelle a cui mancano al massimo ${maxMissing} ingredienti`;
}

/** Perché non c'è niente da mostrare: le parole cercate e i filtri, un caso per ciascuno.
 *
 * «Nessuna ricetta» è un verdetto sul ricettario, e il ricettario del seme ne ha 26:
 * con la soglia semantica di `recipe_search.py` una risposta vuota è diventata
 * raggiungibile per la prima volta, e quasi sempre riguarda le parole cercate o il
 * filtro, non il ricettario. È lo stesso errore che b6ed1d9 ha corretto nel pannello
 * del catalogo («con queste parole», non «in catalogo»), dall'altro lato dell'app.
 * Dove la via d'uscita è scrivere una ricetta, la frase porta a «Nuova» (T3 Consegna 4):
 * l'AI non è più l'ingresso del modulo.
 */
function emptyMessage({
  query,
  maxMissing,
  category,
  ingredientNames,
}: {
  query: string;
  maxMissing: number | null;
  category: string;
  ingredientNames: string[];
}): string {
  const searched = query.trim() !== "";
  if (ingredientNames.length > 0) {
    return (
      `Nessuna ricetta che contenga ${elenco(ingredientNames)}` +
      `${searched ? " con queste parole" : ""}${category ? ` in «${category}»` : ""}` +
      `${frammentoSoglia(maxMissing)}: ` +
      // la via d'uscita è quella vera, e al plurale non è la stessa: ogni
      // ingrediente in più stringe, quindi si esce togliendone uno, non cambiandoli
      (ingredientNames.length === 1
        ? "togli il filtro, o provane un altro."
        : "togli un ingrediente — devono esserci tutti perché una ricetta compaia.")
    );
  }
  if (category) {
    const withSearchFragment = searched ? " con queste parole" : "";
    return (
      `Nessuna ricetta in «${category}»${withSearchFragment}${frammentoSoglia(maxMissing)}: ` +
      "scegli «Tutte» fra le categorie per vedere il resto del ricettario."
    );
  }
  if (searched && maxMissing !== null) {
    return (
      `Nessuna ricetta con queste parole${frammentoSoglia(maxMissing)}: ` +
      "scegli «Tutte» nella scala, o prova con altre parole."
    );
  }
  if (searched) {
    return "Nessuna ricetta con queste parole: provane altre, o scrivine una con «Nuova».";
  }
  if (maxMissing === 0) {
    return (
      "Niente che puoi cucinare con quel che hai in dispensa: alza la soglia, o " +
      "scegli «Tutte» nella scala per vedere tutto il ricettario."
    );
  }
  if (maxMissing !== null) {
    // in cima alla scala non c'è più una soglia da alzare: offrire quel
    // consiglio lì sarebbe impossibile da seguire, non solo inutile
    const wayOut =
      maxMissing === MAX_BUDGET
        ? "scegli «Tutte» nella scala per vedere tutto il ricettario."
        : "alza la soglia, o scegli «Tutte» nella scala per vedere tutto il ricettario.";
    return (
      `Niente da cucinare comprando al massimo ${maxMissing === 1 ? "1 cosa" : `${maxMissing} cose`}: ` +
      wayOut
    );
  }
  return "Il ricettario è vuoto: scrivi la prima ricetta con «Nuova».";
}

function uniqueById<T extends { id: string }>(items: T[]): T[] {
  const seen = new Set<string>();
  return items.filter((item) => {
    if (seen.has(item.id)) return false;
    seen.add(item.id);
    return true;
  });
}

/** Il ricettario (T3 Consegna 4, spec §4.5): «Nuova» in alto, la barra di ricerca con
 * «Filtri» accanto, il pannello dei filtri in linea, la scala «Cosa posso cucinare»
 * sempre a video, e le righe compatte. */
export function RecipeBookScreen() {
  // I filtri nascono da quel che l'app ricorda (Mattia, 2026-09-29): tornando da una
  // ricetta lo schermo rinasce, e deve ritrovare parole, scala, categoria e
  // ingredienti. Ogni cambio si riscrive nella sessionStorage (`recipeFilters.ts`).
  const [filters, setFilters] = useState<RecipeFilters>(() => loadFilters());
  useEffect(() => {
    saveFilters(filters);
  }, [filters]);
  const { query, maxMissing, category, ingredients } = filters;
  const ingredientIds = ingredients.map((i) => i.id);
  const debouncedQuery = useDebounced(query, DEBOUNCE_MS);
  const activeCount = activeFilterCount(filters);

  const [panelOpen, setPanelOpen] = useState(false);
  const panelId = useId();

  function update(patch: Partial<RecipeFilters>) {
    setFilters((current) => ({ ...current, ...patch }));
  }

  // Scegliere due volte lo stesso non stringe niente: sarebbe una pastiglia doppia
  // da togliere due volte e una condizione ripetuta a vuoto nella query. Tornando
  // `current` immutato React non ridisegna e nessuna ricerca riparte.
  function addIngredient(picked: Ingredient) {
    setFilters((current) =>
      current.ingredients.some((i) => i.id === picked.id)
        ? current
        : { ...current, ingredients: [...current.ingredients, picked] }
    );
  }

  function removeIngredient(id: string) {
    setFilters((current) => ({
      ...current,
      ingredients: current.ingredients.filter((i) => i.id !== id),
    }));
  }

  // «Azzera» toglie quel che sta nel pannello, e che il numero su «Filtri» conta:
  // categoria e ingredienti. Parole e scala sono sempre a video, e si cambiano da lì.
  function resetFilters() {
    update({ category: "", ingredients: [] });
  }

  // Il termine sta dentro la chiave, e questo fa due cose che una ricerca scritta
  // a mano non fa. La sicurezza sull'ordine diventa strutturale: una risposta
  // superata atterra sotto la propria chiave e non può sovrascrivere risultati più
  // recenti, senza bisogno di guardarla. E l'errore passa dalla QueryCache che
  // App.tsx aggancia al 401: una sessione scaduta riporta all'accesso, invece di
  // diventare un "ricerca fallita" permanente su uno schermo che non funzionerà
  // mai più. La prima versione di questo schermo sbagliava esattamente lì.
  //
  // Una query a pagine (R4): 8.469 ricette non stanno in una. La chiave è la stessa
  // di prima, quindi gli `invalidateQueries({ queryKey: ["recipes"] })` sparsi
  // nell'app continuano a rinfrescarla; e `useArchiveRecipe` ci toglie una ricetta
  // eliminata sapendo che ogni pagina è una `RecipePage`.
  const {
    data,
    isLoading,
    isError,
    isFetchNextPageError,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    refetch,
    isRefetching,
  } = useInfiniteQuery({
    queryKey: ["recipes", debouncedQuery, maxMissing, category, ingredientIds],
    initialPageParam: 0,
    queryFn: ({ pageParam }) =>
      searchRecipes({
        query: debouncedQuery,
        maxMissing,
        category,
        ingredientIds,
        offset: pageParam,
      }),
    // da dove parte la pagina dopo, e se ce n'è una: vedi `nextPageOffset` in api.ts
    getNextPageParam: (lastPage, allPages) => nextPageOffset(lastPage, allPages),
  });
  // Un inserimento sopra la pagina (l'import che gira) sposta tutto in giù di uno:
  // l'offset fa vedere un doppione, mai un buco, e il doppione si scarta qui.
  const recipes = uniqueById(data?.pages.flatMap((page) => page.recipes) ?? []);
  // il totale più recente: quello dell'ultima pagina arrivata. Il «è solo un minimo»
  // viene dalla stessa pagina (R-D): preso da un'altra, direbbe «almeno» di un numero
  // che il server ha contato per intero, o lo tacerebbe di uno che non ha finito di contare
  const lastPage = data?.pages.at(-1);
  const total = lastPage?.total ?? null;
  const totalIsLowerBound = lastPage?.totalIsLowerBound ?? false;
  // l'errore di una pagina successiva non cancella quel che è già a video
  const searchFailed = isError && !isFetchNextPageError;

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
  // decide un termine o si scarica un lotto. Se la rotta non risponde la scheda non
  // compare: la coda resta raggiungibile dal ☰.
  const { data: importStatus } = useQuery({
    queryKey: ["import-status"],
    queryFn: fetchImportStatus,
  });
  const pendingTerms = importStatus?.pending_terms ?? 0;

  return (
    <Screen
      title="Ricette"
      action={
        // «Nuova» apre il modulo di sempre (R10), da cui la bozza dell'AI si chiede con
        // «Proponi»: l'AI non è più l'ingresso (spec T3 §4.5). La rotta resta quella.
        // Il nome comincia con la scritta a video (label-in-name)
        <Link
          to="/ricette/nuova-ai"
          aria-label="Nuova ricetta"
          className={`${buttonClasses("secondary")} shrink-0`}
        >
          <IconPencilPlus aria-hidden="true" className="size-[1.1em]" stroke={1.8} />
          Nuova
        </Link>
      }
    >
      {/* solo con qualcosa da decidere (spec §4.5): a coda vuota, o con lo stato che non
          arriva, spingerebbe la prima ricetta sotto la piega per niente. La coda resta
          raggiungibile dal ☰, «Ingredienti da abbinare» */}
      {importStatus && pendingTerms > 0 && (
        <SectionEntryCard
          to="/ricette/importa"
          title="Ingredienti da abbinare"
          note={
            `${pendingTerms === 1 ? "1 ingrediente" : `${pendingTerms} ingredienti`}, ` +
            `${importStatus.pending_recipes === 1 ? "1 ricetta in attesa" : `${importStatus.pending_recipes} ricette in attesa`}`
          }
          pending
        />
      )}

      <div className="flex items-center gap-2">
        <div className="relative min-w-0 flex-1">
          <IconSearch
            aria-hidden="true"
            className="pointer-events-none absolute top-1/2 left-3 size-5 -translate-y-1/2 text-ink-faint"
          />
          <input
            id="recipe-search"
            aria-label="Cerca nel ricettario"
            value={query}
            onChange={(e) => update({ query: e.target.value })}
            placeholder="Cerca un piatto o un ingrediente"
            className="pl-10 text-base"
          />
        </div>
        {/* Un pulsante da solo: icona e testo (spec §2). Il numero dei filtri accesi si
            vede e si sente: nel nome, e in una pastiglia accanto alla scritta */}
        <Button
          icon={IconAdjustmentsHorizontal}
          accessibleName={filtersButtonName(activeCount)}
          aria-expanded={panelOpen}
          aria-controls={panelId}
          onClick={() => setPanelOpen((open) => !open)}
          className="shrink-0"
        >
          Filtri
          {activeCount > 0 && (
            <span className="min-w-5 rounded-full bg-brand px-1.5 text-center text-xs font-semibold text-on-brand">
              {activeCount}
            </span>
          )}
        </Button>
      </div>

      <RecipeFiltersPanel
        id={panelId}
        open={panelOpen}
        categories={categories}
        category={category}
        onCategory={(value) => update({ category: value })}
        ingredients={ingredients}
        onPick={addIngredient}
        onRemove={removeIngredient}
        count={isLoading ? "Cerco…" : searchFailed ? null : resultsLabel(total, totalIsLowerBound)}
        onReset={activeCount > 0 ? resetFilters : undefined}
      />

      {/* una constatazione, non un guasto: niente `role`, niente colore d'allarme.
          `=== false` e non `!searchMode?.semantic`, perché "non lo so ancora" e
          "non risponde" non sono "è degradata" */}
      {searchMode?.semantic === false && (
        <p className="pt-2 text-xs text-ink-faint">
          Ricerca solo testuale: trova le parole che scrivi, non i piatti simili.
        </p>
      )}

      <MissingBudgetFilter value={maxMissing} onChange={(value) => update({ maxMissing: value })} />

      {isLoading && <p className="pt-4 text-ink-soft">Cerco…</p>}

      {!isLoading && searchFailed && (
        <ErrorState
          message="Non sono riuscito a cercare nel ricettario."
          onRetry={() => void refetch()}
          retrying={isRefetching}
        />
      )}

      {!isLoading && !searchFailed && recipes.length === 0 && (
        <EmptyState
          title="Nessuna ricetta"
          body={emptyMessage({
            query: debouncedQuery,
            maxMissing,
            category,
            ingredientNames: ingredients.map((i) => i.display_name),
          })}
          action={
            activeCount > 0 ? (
              <Button icon={IconClearAll} onClick={resetFilters}>
                Azzera i filtri
              </Button>
            ) : undefined
          }
        />
      )}

      {!isLoading && !searchFailed && recipes.length > 0 && (
        <ul aria-label="Ricette trovate" className="flex flex-col rounded-2xl bg-card px-3 py-1">
          {recipes.map((recipe) => (
            <RecipeRow key={recipe.id} recipe={recipe} />
          ))}
        </ul>
      )}

      {!isLoading && !searchFailed && hasNextPage && (
        <div className="flex flex-col items-center gap-2 pt-3">
          {/* il bottone resta: riprovare è la via d'uscita, mai un vicolo cieco */}
          {isFetchNextPageError && <Alert>Non sono riuscito a caricarne altre.</Alert>}
          {/* `busy` e non `disabled`: in volo tiene il fuoco (regola dei pulsanti) */}
          <Button onClick={() => void fetchNextPage()} busy={isFetchingNextPage}>
            {isFetchingNextPage ? "Carico…" : "Mostra altre"}
          </Button>
        </div>
      )}
    </Screen>
  );
}

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { RecipeCard } from "./RecipeCard";
import { MissingBudgetFilter, MAX_BUDGET } from "./MissingBudgetFilter";
import { fetchCategories, fetchSearchMode, searchRecipes } from "./api";
import { fetchImportStatus } from "../recipe-import/api";
import { useDebounced } from "../../hooks/useDebounced";
import { Alert } from "../../components/ui/Alert";
import { Screen } from "../../components/ui/Screen";
import { SectionEntryCard } from "../../components/ui/SectionEntryCard";
import { IngredientPicker } from "../../components/IngredientPicker";
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
    return "Nessuna ricetta con queste parole: provane altre, o scrivine una con l'AI.";
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
  return "Nessuna ricetta. Provane una scritta con l'AI.";
}

export function RecipeBookScreen() {
  const [query, setQuery] = useState("");
  // `null` è «Tutte»: l'assenza di soglia, non una soglia larghissima
  const [maxMissing, setMaxMissing] = useState<number | null>(null);
  const [category, setCategory] = useState("");
  // gli ingredienti scelti, non solo i loro id: i nomi servono alle pastiglie del
  // filtro e al messaggio di elenco vuoto, e una seconda chiamata per riaverli
  // sarebbe un giro in rete per qualcosa che l'utente ha appena toccato
  const [ingredients, setIngredients] = useState<Ingredient[]>([]);
  const ingredientIds = ingredients.map((i) => i.id);
  const debouncedQuery = useDebounced(query, DEBOUNCE_MS);

  // Il termine sta dentro la chiave, e questo fa due cose che una ricerca scritta
  // a mano non fa. La sicurezza sull'ordine diventa strutturale: una risposta
  // superata atterra sotto la propria chiave e non può sovrascrivere risultati più
  // recenti, senza bisogno di guardarla. E l'errore passa dalla QueryCache che
  // App.tsx aggancia al 401: una sessione scaduta riporta all'accesso, invece di
  // diventare un "ricerca fallita" permanente su uno schermo che non funzionerà
  // mai più. La prima versione di questo schermo sbagliava esattamente lì.
  const { data: recipes = [], isLoading, isError } = useQuery({
    queryKey: ["recipes", debouncedQuery, maxMissing, category, ingredientIds],
    queryFn: () =>
      searchRecipes({
        query: debouncedQuery,
        maxMissing,
        category,
        ingredientIds,
      }),
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

  // Scegliere due volte lo stesso non stringe niente: sarebbe una pastiglia doppia
  // da togliere due volte e una condizione ripetuta a vuoto nella query. Tornando
  // `current` immutato React non ridisegna e nessuna ricerca riparte.
  function addIngredient(picked: Ingredient) {
    setIngredients((current) =>
      current.some((i) => i.id === picked.id) ? current : [...current, picked]
    );
  }

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
      <SectionEntryCard
        to="/ricette/importa"
        title="Ingredienti da abbinare"
        note={
          importStatus === undefined
            ? "Le decisioni dell'import, da rivedere"
            : importStatus.pending_terms === 0
              ? "Niente in attesa: qui si rivedono le decisioni già prese"
              : `${importStatus.pending_terms === 1 ? "1 ingrediente" : `${importStatus.pending_terms} ingredienti`}, ` +
                `${importStatus.pending_recipes === 1 ? "1 ricetta in attesa" : `${importStatus.pending_recipes} ricette in attesa`}`
        }
        pending={(importStatus?.pending_terms ?? 0) > 0}
      />

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

      <MissingBudgetFilter value={maxMissing} onChange={setMaxMissing} />

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

      {/* il campo resta a video anche con qualcosa già scelto: gli ingredienti si
          sommano, e un campo che sparisce al primo tocco direbbe il contrario */}
      <IngredientPicker
        label="Contiene ingredienti"
        failureNote="Puoi comunque cercare per parole qui sopra."
        kind="food"
        onPick={addIngredient}
      />

      {ingredients.length > 0 && (
        <ul className="flex flex-wrap items-center gap-2">
          {ingredients.map((chosen) => (
            <li
              key={chosen.id}
              className="flex items-center gap-1 rounded-card bg-brand-tint pr-1 pl-3"
            >
              <span className="min-w-0 truncate text-sm text-brand">{chosen.display_name}</span>
              {/* la stessa X con cui si toglie una voce dalla dispensa, e per la
                  stessa ragione il nome accessibile nomina l'ingrediente: su tre
                  pastiglie «Togli» ripetuto identico non dice quale si sta togliendo */}
              <button
                type="button"
                aria-label={`Togli il filtro su ${chosen.display_name}`}
                onClick={() =>
                  setIngredients((current) => current.filter((i) => i.id !== chosen.id))
                }
                className="flex size-11 shrink-0 items-center justify-center rounded-full text-brand"
              >
                <svg
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                  className="size-4"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                >
                  <path d="M6 6l12 12M18 6L6 18" />
                </svg>
              </button>
            </li>
          ))}
        </ul>
      )}

      {isLoading && <p className="pt-4 text-ink-soft">Cerco…</p>}

      {!isLoading && isError && (
        <Alert className="pt-4">
          Non sono riuscito a cercare nel ricettario. Riprova, o scrivine una con l'AI.
        </Alert>
      )}

      {!isLoading && !isError && recipes.length === 0 && (
        <p className="pt-4 text-ink-soft">
          {emptyMessage({
            query: debouncedQuery,
            maxMissing,
            category,
            ingredientNames: ingredients.map((i) => i.display_name),
          })}
        </p>
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

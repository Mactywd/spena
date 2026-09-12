import { useCallback, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { createIngredient, fetchShoppingList, searchIngredients } from "../shopping-list/api";
import { BarcodeScanner } from "./BarcodeScanner";
import { CatalogSearchPanel } from "./CatalogSearchPanel";
import { CustomProductForm } from "./CustomProductForm";
import type { ProductSuggestion } from "./CustomProductForm";
import { lookupBarcode, stockItems } from "./api";
import type { Ingredient, Product, ShoppingItem } from "../../domain/types";

type Resolution =
  | { kind: "loose" }
  | { kind: "product"; product: Product };

// il reparto di un ingrediente nato da un testo libero non lo sappiamo, e
// indovinarlo sarebbe una bugia: "altro" è il reparto che la lista mostra in
// fondo, insieme alle altre voci da chiarire
const UNKNOWN_CATEGORY = "altro";

/**
 * Una voce spuntata ma senza ingrediente abbinato ("un ingrediente che risolve
 * a niente", nelle parole del brief): il testo libero della lista non ha mai
 * trovato un corrispondente. Non può sparire in silenzio dal conto finale, e
 * qui sotto il sistema non inventa niente da solo: l'utente abbina un
 * ingrediente esistente, proprio come quando scrive in lista (Task 18), oppure
 * — quando non esiste, che è il caso normale per un testo spaiato — lo crea.
 */
function MatchIngredientField({
  rawText,
  onMatched,
}: {
  rawText: string;
  onMatched: (ingredient: Ingredient) => void;
}) {
  const [query, setQuery] = useState(rawText);
  const [suggestions, setSuggestions] = useState<Ingredient[]>([]);
  // "searching" finché la prima risposta non arriva: dire "nessuno corrisponde"
  // prima di aver cercato sarebbe falso per la durata del debounce
  const [outcome, setOutcome] = useState<"searching" | "searched" | "failed">("searching");
  // sotto 2 caratteri non vale la pena interrogare il backend, come in AddItemField
  const showSuggestions = query.trim().length >= 2;

  const create = useMutation({
    mutationFn: (text: string) =>
      // name e display_name sono lo stesso testo: il backend normalizza il primo
      // (strip + lower), e inventare noi una forma canonica sarebbe logica di
      // dominio sul client
      createIngredient({ name: text, display_name: text, category: UNKNOWN_CATEGORY }),
    onSuccess: onMatched,
  });

  useEffect(() => {
    if (!showSuggestions) return;
    // stessa guardia di AddItemField: una ricerca lenta e superata non deve
    // sovrascrivere i suggerimenti di una più recente
    let superseded = false;
    const timer = setTimeout(() => {
      searchIngredients(query)
        .then((found) => {
          if (superseded) return;
          setSuggestions(found);
          setOutcome("searched");
        })
        .catch(() => {
          if (superseded) return;
          setSuggestions([]);
          setOutcome("failed");
        });
    }, 180);
    return () => {
      superseded = true;
      clearTimeout(timer);
    };
  }, [query, showSuggestions]);

  const trimmed = query.trim();

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-amber-300 bg-amber-50 p-3">
      <p className="text-sm text-amber-800">
        «{rawText}» non è abbinata a un ingrediente: scegline uno per poterla sistemare.
      </p>
      <label className="text-sm">
        Abbina un ingrediente
        <input
          aria-label={`Abbina un ingrediente per ${rawText}`}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOutcome("searching");
          }}
          className="mt-1 w-full rounded border px-3 py-3 text-base"
        />
      </label>
      {showSuggestions && suggestions.length > 0 && (
        <ul role="listbox" className="overflow-hidden rounded-lg border border-neutral-200">
          {suggestions.map((ingredient) => (
            <li key={ingredient.id}>
              <button
                type="button"
                role="option"
                aria-selected={false}
                onClick={() => onMatched(ingredient)}
                className="w-full px-3 py-3 text-left text-sm"
              >
                {ingredient.display_name}
                <span className="ml-2 text-xs text-neutral-400">{ingredient.category}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {/* una voce arriva qui proprio perché il suo testo non somigliava a niente:
          cercare lo stesso testo è il caso in cui è più probabile non trovare
          nulla, e senza una via d'uscita quella voce resterebbe in lista per
          sempre. Crearlo è l'unica uscita, e nessun task successivo la prevede. */}
      {showSuggestions && outcome === "searched" && suggestions.length === 0 && (
        <p className="text-sm text-amber-800">
          Nessun ingrediente corrisponde. Puoi crearlo adesso: finisce nel reparto «
          {UNKNOWN_CATEGORY}» e la voce diventa sistemabile.
        </p>
      )}
      {showSuggestions && outcome === "failed" && (
        <p role="alert" className="text-sm text-red-600">
          La ricerca degli ingredienti non risponde. Riprova a scrivere, oppure crealo.
        </p>
      )}
      {showSuggestions && outcome !== "searching" && suggestions.length === 0 && (
        <button
          type="button"
          onClick={() => create.mutate(trimmed)}
          disabled={create.isPending}
          className="rounded-lg bg-amber-700 px-4 py-3 text-sm text-white disabled:opacity-40"
        >
          Crea l'ingrediente «{trimmed}»
        </button>
      )}
      {create.isError && (
        <p role="alert" className="text-sm text-red-600">
          Non sono riuscito a creare l'ingrediente. Forse esiste già con un altro nome: cercalo
          qui sopra, oppure riprova.
        </p>
      )}
    </div>
  );
}

export function StockingScreen() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: items = [], isLoading, isError, refetch } = useQuery({
    queryKey: ["shopping-list", "checked"],
    queryFn: () => fetchShoppingList(["checked"]),
  });

  const [resolved, setResolved] = useState<Record<string, Resolution>>({});
  // voci senza ingredient_id, abbinate a mano in questo schermo
  const [matchedIngredient, setMatchedIngredient] = useState<Record<string, Ingredient>>({});
  const [scanningFor, setScanningFor] = useState<ShoppingItem | null>(null);
  // la seconda strada della spec §8.2. Un pannello alla volta: due riquadri aperti
  // sulla stessa voce direbbero due cose diverse su cosa sta per entrare in dispensa
  const [searchingFor, setSearchingFor] = useState<ShoppingItem | null>(null);
  const [manualCode, setManualCode] = useState("");
  const [creatingFor, setCreatingFor] = useState<
    { item: ShoppingItem; barcode: string; suggestion: ProductSuggestion | null } | null
  >(null);

  function effectiveIngredientId(item: ShoppingItem): string | null {
    return item.ingredient_id ?? matchedIngredient[item.id]?.id ?? null;
  }

  const stock = useMutation({
    mutationFn: () =>
      stockItems(
        Object.entries(resolved)
          .map(([itemId, resolution]) => {
            const item = items.find((i) => i.id === itemId);
            const ingredientId = item ? effectiveIngredientId(item) : null;
            if (!ingredientId) return null;
            return {
              shopping_item_id: itemId,
              ingredient_id: ingredientId,
              product_id: resolution.kind === "product" ? resolution.product.id : null,
            };
          })
          .filter((entry): entry is NonNullable<typeof entry> => entry !== null)
      ),
    onSuccess: () => {
      // la lista della spesa tiene in cache le stesse voci: senza invalidare
      // questo prefisso, tornando a "Lista" le voci appena sistemate restano
      // ancora spuntate, come se non fosse successo niente
      queryClient.invalidateQueries({ queryKey: ["shopping-list"] });
      navigate("/dispensa");
    },
  });

  // Il lookup passa da una mutazione e non da una chiamata nuda per due ragioni:
  // un errore non resta una promise rifiutata che nessuno guarda (prima, con la
  // rete giù, premere Invio non faceva assolutamente niente), e un 401 passa
  // dalla MutationCache di App.tsx, cioè riporta all'accesso come ogni altra
  // scrittura invece di morire qui.
  const lookup = useMutation({
    mutationFn: ({ code }: { item: ShoppingItem; code: string }) => lookupBarcode(code),
    onSuccess: (result, { item, code }) => {
      const product = result.product;
      if (product) {
        setResolved((prev) => ({ ...prev, [item.id]: { kind: "product", product } }));
      } else {
        // conosciuto da Open Food Facts ma non ancora in catalogo: il modulo si
        // apre precompilato con quel che si sa già, non da zero. Ignoto anche
        // lì, o servizio giù: stesso modulo, stavolta vuoto — mai un muro.
        setCreatingFor({ item, barcode: code, suggestion: result.suggestion });
      }
      setScanningFor(null);
    },
  });
  const { mutate: lookupCode } = lookup;
  const failedLookup = lookup.isError ? lookup.variables : null;

  // Senza useCallback, ogni tasto premuto nel campo del codice manuale (un
  // sibling re-render, non legato allo scanner) creerebbe una nuova identità
  // di `onDetected`, e l'effetto di BarcodeScanner ne dipende: la fotocamera
  // si spegnerebbe e si riaccenderebbe a ogni carattere digitato. `mutate` di
  // react-query è stabile, quindi lo resta anche questa.
  const handleDetected = useCallback(
    (code: string) => {
      if (scanningFor) lookupCode({ item: scanningFor, code });
    },
    [scanningFor, lookupCode]
  );

  function openCatalog(item: ShoppingItem) {
    setScanningFor(null);
    setSearchingFor(item);
  }

  function openScanner(item: ShoppingItem) {
    setSearchingFor(null);
    // Il codice digitato per un'altra voce non deve sopravvivere all'apertura: il
    // residuo si agganciava alla voce nuova senza nessuna conferma intermedia.
    // Si svuota qui, all'apertura, e non dopo il lookup: finché la chiamata è in
    // volo o è andata male, quel che l'utente ha digitato resta dov'è, come il
    // campo di AddItemField in Task 18.
    setManualCode("");
    lookup.reset();
    setScanningFor(item);
  }

  function createByHand(item: ShoppingItem, barcode: string) {
    setCreatingFor({ item, barcode, suggestion: null });
    setScanningFor(null);
    setSearchingFor(null);
  }

  return (
    <div className="p-4">
      <h1 className="pb-3 text-xl font-semibold">Sistema la spesa</h1>

      {isLoading && <p className="text-neutral-500">Carico…</p>}
      {/* un caricamento fallito non è una lista vuota: dire "non hai spuntato
          niente" a chi è tornato dalla spesa con le borse in mano è una bugia,
          e senza riprova non gli resta niente da fare */}
      {isError && (
        <div className="flex flex-col items-start gap-2">
          <p role="alert" className="text-sm text-red-600">
            Non sono riuscito a caricare la spesa da sistemare. La lista non è vuota: non l'ho
            letta.
          </p>
          <button
            type="button"
            onClick={() => void refetch()}
            className="rounded-lg border px-4 py-3 text-sm"
          >
            Riprova
          </button>
        </div>
      )}
      {!isLoading && !isError && items.length === 0 && (
        <p className="text-neutral-500">Niente da sistemare. Spunta prima qualcosa in lista.</p>
      )}

      <ul className="divide-y divide-neutral-100">
        {items.map((item) => {
          const resolution = resolved[item.id];
          const ingredientId = effectiveIngredientId(item);
          return (
            <li key={item.id} className="flex flex-col gap-2 py-3">
              <div className="flex items-center justify-between gap-2">
                <span className={resolution ? "font-medium text-emerald-700" : ""}>
                  {item.raw_text}
                </span>
                {resolution?.kind === "product" && (
                  <span className="text-sm text-neutral-500">{resolution.product.name}</span>
                )}
              </div>

              {!resolution && !ingredientId && (
                <MatchIngredientField
                  rawText={item.raw_text}
                  onMatched={(ingredient) =>
                    setMatchedIngredient((prev) => ({ ...prev, [item.id]: ingredient }))
                  }
                />
              )}

              {!resolution && ingredientId && (
                // wrap: su 375px due pulsanti con il nome della voce dentro non
                // stanno su una riga, e stringerli li rende difficili da toccare
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => openScanner(item)}
                    className="rounded border px-4 py-3 text-sm"
                  >
                    {/* il nome della voce serve al nome accessibile, non all'occhio:
                        letto da uno screen reader distingue i pulsanti, visibile
                        stringerebbe la riga senza aggiungere niente */}
                    Codice a barre<span className="sr-only"> per {item.raw_text}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => openCatalog(item)}
                    className="rounded border px-4 py-3 text-sm"
                  >
                    Cerca a catalogo<span className="sr-only"> per {item.raw_text}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      setResolved((prev) => ({ ...prev, [item.id]: { kind: "loose" } }))
                    }
                    className="rounded border px-4 py-3 text-sm"
                  >
                    Sfuso, senza marca<span className="sr-only">: {item.raw_text}</span>
                  </button>
                </div>
              )}
            </li>
          );
        })}
      </ul>

      {scanningFor && (
        <div className="mt-4 flex flex-col gap-3 rounded-lg border p-4">
          <BarcodeScanner
            onDetected={handleDetected}
            onCancel={() => setScanningFor(null)}
          />
          <label className="text-sm">
            Codice a barre
            <input
              aria-label="Codice a barre"
              value={manualCode}
              onChange={(e) => setManualCode(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") lookupCode({ item: scanningFor, code: manualCode });
              }}
              className="mt-1 w-full rounded border px-3 py-3 text-base"
            />
          </label>
          {lookup.isPending && <p className="text-sm text-neutral-500">Cerco il codice…</p>}
          {/* anche il fallimento di rete degrada al manuale: un errore muto qui
              era il muro più silenzioso dello schermo */}
          {failedLookup && (
            <div className="flex flex-col items-start gap-2">
              <p role="alert" className="text-sm text-red-600">
                Non sono riuscito a leggere il codice. Riprova, oppure crea il prodotto a mano.
              </p>
              <button
                type="button"
                onClick={() => createByHand(failedLookup.item, failedLookup.code)}
                className="rounded-lg border px-4 py-3 text-sm"
              >
                Crea il prodotto a mano
              </button>
            </div>
          )}
        </div>
      )}

      {searchingFor && effectiveIngredientId(searchingFor) && (
        <CatalogSearchPanel
          // come per CustomProductForm: senza key React riusa l'istanza passando da
          // una voce all'altra, e il campo resterebbe sul testo della voce di prima
          key={searchingFor.id}
          itemLabel={searchingFor.raw_text}
          ingredientId={effectiveIngredientId(searchingFor) as string}
          onPicked={(product) => {
            setResolved((prev) => ({ ...prev, [searchingFor.id]: { kind: "product", product } }));
            setSearchingFor(null);
          }}
          onCreateByHand={() => createByHand(searchingFor, "")}
          onCancel={() => setSearchingFor(null)}
        />
      )}

      {creatingFor && effectiveIngredientId(creatingFor.item) && (
        <div className="mt-4">
          <CustomProductForm
            // senza key React riusa l'istanza passando da una voce all'altra: i
            // campi restano quelli di prima mentre ingrediente e codice sono già
            // i nuovi, e si salva il prodotto sbagliato sotto l'ingrediente
            // sbagliato, in silenzio e per sempre
            key={`${creatingFor.item.id}:${creatingFor.barcode}`}
            ingredientId={effectiveIngredientId(creatingFor.item) as string}
            itemLabel={creatingFor.item.raw_text}
            barcode={creatingFor.barcode}
            suggestion={creatingFor.suggestion}
            onCreated={(product) => {
              setResolved((prev) => ({
                ...prev,
                [creatingFor.item.id]: { kind: "product", product },
              }));
              setCreatingFor(null);
            }}
            onCancel={() => setCreatingFor(null)}
          />
        </div>
      )}

      {stock.isError && (
        <p role="alert" className="mt-4 text-sm text-red-600">
          Non sono riuscito a mettere in dispensa. Quel che hai confermato è ancora qui: riprova.
        </p>
      )}

      <button
        type="button"
        onClick={() => stock.mutate()}
        disabled={Object.keys(resolved).length === 0 || stock.isPending}
        className="mt-6 w-full rounded-lg bg-emerald-700 px-4 py-3 text-white disabled:opacity-40"
      >
        Metti in dispensa
      </button>
    </div>
  );
}

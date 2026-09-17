import { useCallback, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { createIngredient, fetchShoppingList, searchIngredients } from "../shopping-list/api";
import { BarcodeScanner } from "./BarcodeScanner";
import { CatalogSearchPanel } from "./CatalogSearchPanel";
import { CustomProductForm } from "./CustomProductForm";
import type { ProductSuggestion } from "./CustomProductForm";
import { lookupBarcode, stockItems } from "./api";
import { OTHER_INGREDIENT } from "./wording";
import { ApiError } from "../../api/client";
import type { Ingredient, Product, ShoppingItem } from "../../domain/types";
import { buttonClasses } from "../../components/ui/buttonClasses";
import { BackLink } from "../../components/BackLink";

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
    <div className="flex flex-col gap-2 rounded-card border border-low/30 bg-low-tint p-3">
      <p className="text-sm text-low">
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
          className="mt-1.5"
        />
      </label>
      {showSuggestions && suggestions.length > 0 && (
        <ul role="listbox" className="divide-y divide-line overflow-hidden rounded-card bg-card">
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
                <span className="ml-2 text-xs text-ink-faint">{ingredient.category}</span>
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
        <p className="text-sm text-low">
          Nessun ingrediente corrisponde. Puoi crearlo adesso: finisce nel reparto «
          {UNKNOWN_CATEGORY}» e la voce diventa sistemabile.
        </p>
      )}
      {showSuggestions && outcome === "failed" && (
        <p role="alert" className="text-sm text-danger">
          La ricerca degli ingredienti non risponde. Riprova a scrivere, oppure crealo.
        </p>
      )}
      {showSuggestions && outcome !== "searching" && suggestions.length === 0 && (
        <button
          type="button"
          onClick={() => create.mutate(trimmed)}
          disabled={create.isPending}
          className={buttonClasses("warn")}
        >
          Crea l'ingrediente «{trimmed}»
        </button>
      )}
      {create.isError && (
        <p role="alert" className="text-sm text-danger">
          Non sono riuscito a creare l'ingrediente. Forse esiste già con un altro nome: cercalo
          qui sopra, oppure riprova.
        </p>
      )}
    </div>
  );
}

/** Perché la sistemazione è fallita, in una frase che dice cosa fare.
 *
 * «Riprova» da solo era un vicolo cieco su due delle tre cause: la sistemazione è
 * tutto-o-niente, quindi lo stesso corpo rimandato dà lo stesso errore per sempre.
 * Riprovare è l'azione giusta solo quando la causa è passeggera (rete, backend
 * giù); le altre due si risolvono cambiando una scelta o rileggendo la lista, e
 * vanno nominate. Il 409 non dovrebbe più essere raggiungibile dall'interfaccia
 * (vedi lookup.onSuccess e il filtro di CatalogSearchPanel): se arriva, la via
 * d'uscita è «Cambia» sulla voce sbagliata.
 */
function stockFailureMessage(error: unknown): string {
  const status = error instanceof ApiError ? error.status : null;
  const nothingWritten =
    "Non ho messo in dispensa niente, e quel che hai confermato è ancora qui";
  if (status === 409) {
    return (
      `${nothingWritten}: un prodotto scelto è di un altro ingrediente. ` +
      "Premi «Cambia» su quella voce e scegline un altro, o confermala come sfusa."
    );
  }
  if (status === 404) {
    return (
      `${nothingWritten}: una voce o un prodotto non esiste più. ` +
      "Rileggi la spesa da sistemare qui sotto, poi riprova."
    );
  }
  return (
    `${nothingWritten}: riprova. ` +
    "Se insiste, è il backend che non risponde: le conferme restano su questo schermo."
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
  // un codice letto che porta al prodotto di un altro ingrediente: non è una
  // risoluzione, è la ragione per cui non c'è (vedi lookup.onSuccess)
  const [mismatch, setMismatch] = useState<{ item: ShoppingItem; product: Product } | null>(
    null
  );

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
      setMismatch(null);
      if (product && product.ingredient_id !== effectiveIngredientId(item)) {
        // `GET /products/barcode/{code}` cerca per codice e basta, quindi la
        // referenza che torna può essere di un altro ingrediente: «Passata Mutti»
        // creata sotto `pomodoro` e riletta su una voce risolta a `passata`.
        // Adottarla qui faceva fallire con 409 l'intera sistemazione — che è
        // tutto-o-niente — comprese le voci risolte bene, e il 409 si ripresenta
        // identico a ogni tentativo. Il controllo del backend resta l'ultima
        // difesa; l'interfaccia non deve arrivarci.
        setMismatch({ item, product });
        return;
      }
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

  /** Disfa la conferma di una riga, lasciando intatte le altre.
   *
   * Senza questo, una scansione sbagliata già confermata non si poteva correggere
   * in nessun modo (i tre pulsanti stanno sotto `!resolution`): l'unica uscita era
   * navigare via, cioè perdere le conferme di tutto il giro di spesa. Azzera anche
   * l'errore della sistemazione, che parlava di un tentativo fatto su scelte che
   * da adesso non sono più quelle.
   */
  function changeResolution(item: ShoppingItem) {
    setResolved((prev) => {
      const next = { ...prev };
      delete next[item.id];
      return next;
    });
    stock.reset();
  }

  function openScanner(item: ShoppingItem) {
    setSearchingFor(null);
    setMismatch(null);
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

  // pt-2, non pt-4: il ritorno porta già la sua altezza da bersaglio,
  // combacia con quel che Screen fa da sé quando c'è un back
  return (
    <div className="px-4 pt-2 pb-4">
      <BackLink to="/lista" label="Lista" />
      <h1 className="pb-3 text-xl font-semibold">Sistema la spesa</h1>

      {isLoading && <p className="text-ink-soft">Carico…</p>}
      {/* un caricamento fallito non è una lista vuota: dire "non hai spuntato
          niente" a chi è tornato dalla spesa con le borse in mano è una bugia,
          e senza riprova non gli resta niente da fare */}
      {isError && (
        <div className="flex flex-col items-start gap-2">
          <p role="alert" className="text-sm text-danger">
            Non sono riuscito a caricare la spesa da sistemare. La lista non è vuota: non l'ho
            letta.
          </p>
          <button
            type="button"
            onClick={() => void refetch()}
            className={buttonClasses("secondary")}
          >
            Riprova
          </button>
        </div>
      )}
      {!isLoading && !isError && items.length === 0 && (
        <p className="text-ink-soft">Niente da sistemare. Spunta prima qualcosa in lista.</p>
      )}

      <ul className="divide-y divide-line">
        {items.map((item) => {
          const resolution = resolved[item.id];
          const ingredientId = effectiveIngredientId(item);
          return (
            <li key={item.id} className="flex flex-col gap-2 py-3">
              <div className="flex items-center justify-between gap-2">
                <span className={resolution ? "font-medium text-brand" : ""}>
                  {item.raw_text}
                </span>
                {resolution?.kind === "product" && (
                  <span className="text-sm text-ink-soft">{resolution.product.name}</span>
                )}
                {resolution && (
                  <button
                    type="button"
                    onClick={() => changeResolution(item)}
                    className={`${buttonClasses("secondary")} shrink-0`}
                  >
                    Cambia<span className="sr-only"> la scelta per {item.raw_text}</span>
                  </button>
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
                    className={buttonClasses("secondary")}
                  >
                    {/* il nome della voce serve al nome accessibile, non all'occhio:
                        letto da uno screen reader distingue i pulsanti, visibile
                        stringerebbe la riga senza aggiungere niente */}
                    Codice a barre<span className="sr-only"> per {item.raw_text}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => openCatalog(item)}
                    className={buttonClasses("secondary")}
                  >
                    Cerca a catalogo<span className="sr-only"> per {item.raw_text}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      setResolved((prev) => ({ ...prev, [item.id]: { kind: "loose" } }))
                    }
                    className={buttonClasses("secondary")}
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
        <div className="mt-4 flex flex-col gap-3 rounded-card bg-card p-4">
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
              className="mt-1.5"
            />
          </label>
          {lookup.isPending && <p className="text-sm text-ink-soft">Cerco il codice…</p>}
          {/* il codice esiste in catalogo, ma sotto un altro ingrediente: la stessa
              frase del pannello del catalogo, perché è lo stesso fatto. Non si
              scrive nessuna risoluzione, quindi i tre pulsanti della voce sono
              ancora là sopra: leggere un altro codice, cercare a catalogo o
              confermare sfuso restano tutte aperte. */}
          {mismatch && mismatch.item.id === scanningFor.id && (
            <p role="alert" className="text-sm text-danger">
              «{mismatch.product.name}» {OTHER_INGREDIENT.one}. Leggi un altro codice, cercalo a
              catalogo, oppure conferma «{mismatch.item.raw_text}» come sfuso.
            </p>
          )}
          {/* anche il fallimento di rete degrada al manuale: un errore muto qui
              era il muro più silenzioso dello schermo */}
          {failedLookup && (
            <div className="flex flex-col items-start gap-2">
              <p role="alert" className="text-sm text-danger">
                Non sono riuscito a leggere il codice. Riprova, oppure crea il prodotto a mano.
              </p>
              <button
                type="button"
                onClick={() => createByHand(failedLookup.item, failedLookup.code)}
                className={buttonClasses("secondary")}
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
        <div className="mt-4 flex flex-col items-start gap-2">
          <p role="alert" className="text-sm text-danger">
            {stockFailureMessage(stock.error)}
          </p>
          {/* un 404 è l'unico caso in cui riprovare così com'è non può riuscire: la
              lista va riletta. Le risoluzioni sono indicizzate per id di voce,
              quindi sopravvivono alla rilettura — e quella della voce sparita viene
              scartata da sé nel corpo della richiesta. */}
          {stock.error instanceof ApiError && stock.error.status === 404 && (
            <button
              type="button"
              onClick={() => {
                // anche l'errore va via: lasciarlo acceso dopo la rilettura
                // direbbe che c'è ancora un guasto su uno schermo già rimesso in
                // sesto
                stock.reset();
                void refetch();
              }}
              className={buttonClasses("secondary")}
            >
              Rileggi la spesa da sistemare
            </button>
          )}
        </div>
      )}

      <button
        type="button"
        onClick={() => stock.mutate()}
        disabled={Object.keys(resolved).length === 0 || stock.isPending}
        className={`${buttonClasses("primary", "block")} mt-6`}
      >
        Metti in dispensa
      </button>
    </div>
  );
}

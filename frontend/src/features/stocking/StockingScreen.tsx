import { useCallback, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  createIngredient,
  fetchShoppingList,
  patchShoppingItem,
  searchIngredients,
} from "../shopping-list/api";
import { BarcodeScanner } from "./BarcodeScanner";
import { CatalogSearchPanel } from "./CatalogSearchPanel";
import { CustomProductForm } from "./CustomProductForm";
import type { ProductSuggestion } from "./CustomProductForm";
import { lookupBarcode, stockItems } from "./api";
import { OTHER_INGREDIENT } from "./wording";
import { ApiError } from "../../api/client";
import type { Ingredient, Product, ShoppingItem } from "../../domain/types";
import { buttonClasses } from "../../components/ui/buttonClasses";
import { Alert } from "../../components/ui/Alert";
import { BackLink } from "../../components/BackLink";
import { FOOD_CATEGORIES, NON_FOOD_CATEGORIES } from "../../domain/categories";
import { EXPIRY_INPUT_MAX } from "../pantry/expiryLabels";

type Resolution =
  | { kind: "loose" }
  // `barcode`: il codice letto per la voce prima di scegliere il prodotto a
  // catalogo (S8), che la sistemazione porta al backend perché lo dia al
  // prodotto se non ne ha. Solo quella scelta lo porta: il prodotto trovato dal
  // codice ce l'ha già, e quello creato a mano lo riceve alla creazione
  | { kind: "product"; product: Product; barcode?: string };

/** L'ingrediente omonimo che il 409 di `POST /ingredients` porta in `existing`, se
 * l'errore è quello. Ogni altro fallimento torna `null` e tiene il suo messaggio. */
function existingIngredient(error: unknown): Ingredient | null {
  if (!(error instanceof ApiError) || error.status !== 409) return null;
  const body = error.body;
  if (body === null || typeof body !== "object" || !("existing" in body)) return null;
  return (body as { existing: Ingredient }).existing ?? null;
}

/** Il nome di Open Food Facts accanto alla domanda, in una frase sola. */
function describeSuggestion(suggestion: ProductSuggestion): string {
  const what = suggestion.name ? `«${suggestion.name}»` : "senza nome";
  const by = suggestion.brand ? `, di ${suggestion.brand}` : "";
  return `Su Open Food Facts è ${what}${by}.`;
}

/**
 * La domanda prima del modulo, quando un codice nuovo al catalogo è noto a Open
 * Food Facts (S20). Il modulo precompilato si apriva direttamente per
 * l'ingrediente della voce, con «Salva» pieno: gli spaghetti letti sulla voce
 * «pomodoro» diventavano per sempre un prodotto di pomodoro, e le ricette al
 * pomodoro cucinabili con la pasta. La domanda si fa sempre, senza confrontare i
 * nomi: «Spaghetti n.5» e «pomodoro» non si somigliano, ma nemmeno «Passata
 * Rustica» e «passata di pomodoro» in modo affidabile, e un confronto che a volte
 * tace è peggio di una domanda che costa un tocco.
 */
function OffSuggestionQuestion({
  ingredientName,
  suggestion,
  onYes,
  onNo,
}: {
  ingredientName: string;
  suggestion: ProductSuggestion;
  onYes: () => void;
  onNo: () => void;
}) {
  return (
    <div className="flex flex-col gap-3 rounded-card bg-card p-4">
      <h3 className="text-lg font-semibold">È un «{ingredientName}»?</h3>
      <p className="text-ink">{describeSuggestion(suggestion)}</p>
      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={onYes} className={buttonClasses("primary")}>
          Sì
        </button>
        <button type="button" onClick={onNo} className={buttonClasses("secondary")}>
          No, è un'altra cosa
        </button>
      </div>
    </div>
  );
}

/**
 * Una voce spuntata ma senza ingrediente abbinato ("un ingrediente che risolve
 * a niente", nelle parole del brief): il testo libero della lista non ha mai
 * trovato un corrispondente. Non può sparire in silenzio dal conto finale, e
 * qui sotto il sistema non inventa niente da solo: l'utente abbina un
 * ingrediente esistente, proprio come quando scrive in lista (Task 18), oppure
 * lo crea. Le due strade stanno una sotto l'altra e sono sempre entrambe aperte:
 * legare la seconda all'assenza della prima è il difetto S6, corretto il
 * 2026-09-20 (vedi il commento sopra la creazione).
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

  // Il reparto non si indovina più: si chiede. Il commento che stava qui diceva
  // «indovinarlo sarebbe una bugia», e aveva ragione — la correzione non è
  // indovinare meglio. Parte da «altro», che è dove finiva d'ufficio: chi non ha
  // niente da dire fa esattamente quello che faceva prima.
  const [category, setCategory] = useState<string>("altro");

  const create = useMutation({
    mutationFn: async (text: string) => {
      try {
        // name e display_name sono lo stesso testo: il backend normalizza il primo
        // (strip + lower), e inventare noi una forma canonica sarebbe logica di
        // dominio sul client
        return await createIngredient({ name: text, display_name: text, category });
      } catch (error) {
        // Il nome c'è già (S19): il 409 porta l'ingrediente che ce l'ha, e quello
        // si aggancia. Prima finiva in «forse esiste già con un altro nome» —
        // esisteva con lo stesso, ed era il primo suggerimento qui sopra. Per lo
        // stesso motivo niente confronto di nomi qui: chi è «lo stesso nome» lo
        // decide il backend, che lo ha appena rifiutato.
        const existing = existingIngredient(error);
        if (existing) return existing;
        throw error;
      }
    },
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
      {/* Questa frase vale solo quando la ricerca non ha trovato niente, e per un
          po' ha deciso anche se si potesse creare: era la premessa sbagliata che
          «non è stato scelto un ingrediente» significhi «non ne esiste uno
          simile». Una voce arriva qui perché in lista è stato scritto testo
          libero senza toccare un suggerimento — la somiglianza non c'entra, e
          infatti «cera per pavimenti» ne pescava sette, `Pera` compresa. La
          creazione sta più sotto e non dipende più da questo. */}
      {showSuggestions && outcome === "searched" && suggestions.length === 0 && (
        <p className="text-sm text-low">
          Nessun ingrediente corrisponde. Puoi crearlo adesso: scegli il reparto e la
          voce diventa sistemabile.
        </p>
      )}
      {showSuggestions && outcome === "failed" && (
        <p role="alert" className="text-sm text-danger">
          La ricerca degli ingredienti non risponde. Riprova a scrivere, oppure crealo.
        </p>
      )}
      {/* Sempre, appena la ricerca ha risposto: è l'unico posto dell'app che crea
          un ingrediente (`createIngredient` ha un solo chiamante), e la dispensa
          manda proprio qui quando il suo selettore fallisce. Nasconderla dietro
          «nessun suggerimento» la rendeva di fatto irraggiungibile — misurato in
          produzione: di sette nomi plausibili di prodotti per la casa, tutti e
          sette pescavano almeno un suggerimento. Con dei suggerimenti davanti
          pesa meno (secondary, non warn): resta la seconda scelta, non sparisce. */}
      {showSuggestions && outcome !== "searching" && (
        <>
          <label className="text-sm">
            Reparto
            <select
              aria-label="Reparto"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="mt-1.5"
            >
              {FOOD_CATEGORIES.map((name) => (
                <option key={name} value={name}>{name}</option>
              ))}
              {/* staccati, perché sono un'altra cosa: non è un reparto in più del
                  supermercato, è la metà dell'anagrafica che le ricette non vedono */}
              <optgroup label="Non alimentari">
                {NON_FOOD_CATEGORIES.map((name) => (
                  <option key={name} value={name}>{name}</option>
                ))}
              </optgroup>
            </select>
          </label>
          <button
            type="button"
            onClick={() => create.mutate(trimmed)}
            disabled={create.isPending}
            className={buttonClasses(suggestions.length > 0 ? "secondary" : "warn")}
          >
            Crea l'ingrediente «{trimmed}»
          </button>
        </>
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
  // La scadenza scritta per voce, indicizzata come `resolved`: opzionale, e
  // il caso normale è non scriverla mai. `openExpiryFor` è il tocco che la
  // fa comparire — dieci campi vuoti sarebbero rumore permanente su uno
  // schermo già il più denso dell'app, per chi la scadenza non la scrive mai.
  const [expiry, setExpiry] = useState<Record<string, string>>({});
  const [openExpiryFor, setOpenExpiryFor] = useState<Record<string, boolean>>({});
  // voci senza ingredient_id, abbinate a mano in questo schermo
  const [matchedIngredient, setMatchedIngredient] = useState<Record<string, Ingredient>>({});
  const [scanningFor, setScanningFor] = useState<ShoppingItem | null>(null);
  // la seconda strada della spec §8.2. Un pannello alla volta: due riquadri aperti
  // sulla stessa voce direbbero due cose diverse su cosa sta per entrare in dispensa
  const [searchingFor, setSearchingFor] = useState<ShoppingItem | null>(null);
  const [manualCode, setManualCode] = useState("");
  const [creatingFor, setCreatingFor] = useState<{
    item: ShoppingItem;
    barcode: string;
    suggestion: ProductSuggestion | null;
    lookedUp?: "not_found" | "failed";
  } | null>(null);
  // il codice nuovo al catalogo che Open Food Facts conosce: prima del modulo, la
  // domanda (vedi OffSuggestionQuestion)
  const [confirmingFor, setConfirmingFor] = useState<
    { item: ShoppingItem; barcode: string; suggestion: ProductSuggestion } | null
  >(null);
  // un codice nuovo al catalogo la cui cifra di controllo non torna: si ferma nel
  // pannello del codice, correggibile, finché chi l'ha letto non lo usa lo stesso
  const [badCode, setBadCode] = useState<
    { item: ShoppingItem; code: string; suggestion: ProductSuggestion | null } | null
  >(null);
  // S19: l'abbinamento fatto qui e non scritto sulla voce, con l'ingrediente per
  // riprovare. La voce resta sistemabile lo stesso, dal match locale
  const [matchNotSaved, setMatchNotSaved] = useState<Record<string, Ingredient>>({});
  // un codice letto che porta al prodotto di un altro ingrediente: non è una
  // risoluzione, è la ragione per cui non c'è (vedi lookup.onSuccess)
  const [mismatch, setMismatch] = useState<{ item: ShoppingItem; product: Product } | null>(
    null
  );
  // Il codice letto per una voce e rimasto senza prodotto — ignoto al catalogo, o
  // lookup fallito — indicizzato come `resolved` (S8). Chi poi chiude il modulo
  // e passa dal catalogo, lì crea il prodotto a mano o ne sceglie uno esistente:
  // senza questo il codice si perdeva, e la scansione successiva non trovava
  // niente. Lo sfuso non lo legge: non c'è un prodotto a cui darlo.
  const [unlinkedCode, setUnlinkedCode] = useState<Record<string, string>>({});

  function rememberUnlinkedCode(item: ShoppingItem, code: string | null) {
    setUnlinkedCode((prev) => {
      const next = { ...prev };
      if (code) next[item.id] = code;
      else delete next[item.id];
      return next;
    });
  }

  function effectiveIngredientId(item: ShoppingItem): string | null {
    return item.ingredient_id ?? matchedIngredient[item.id]?.id ?? null;
  }

  // lo stesso ragionamento di effectiveIngredientId: la voce può avere il suo
  // ingrediente dalla lista, oppure averlo appena abbinato qui dentro
  //
  // `null` vuol dire "non lo so" e fa mostrare i campi nutrienti come per un
  // alimentare (CustomProductForm.isNonFood di default è false). Al punto di
  // chiamata (sotto, <CustomProductForm isNonFood={effectiveKind(...) ===
  // "non_food"}>) questo `null` non è raggiungibile: il modulo si apre solo se
  // effectiveIngredientId(item) è valorizzato, e reparto e identificativo
  // arrivano sempre insieme dalla stessa fonte — sia dal backend
  // (app/api/shopping.py scrive ingredient_kind accanto a ingredient_id dallo
  // stesso oggetto Ingredient, che non ha kind nullable) sia da un match fatto
  // qui dentro. Se un giorno il backend tornasse un ingredient_id senza il suo
  // ingredient (kind compreso), questo `null` tornerebbe raggiungibile e un
  // detersivo mostrerebbe di nuovo le calorie, senza che nessun test se ne
  // accorga.
  function effectiveKind(item: ShoppingItem): "food" | "non_food" | null {
    return item.ingredient_kind ?? matchedIngredient[item.id]?.kind ?? null;
  }

  // lo stesso nome canonico nei due casi: `ingredient_name` del backend è
  // `ingredient.name`, non `display_name`
  function effectiveIngredientName(item: ShoppingItem): string {
    return item.ingredient_name ?? matchedIngredient[item.id]?.name ?? item.raw_text;
  }

  // S19: l'abbinamento viveva solo in `matchedIngredient` fino a «Metti in
  // dispensa». Una voce che oggi non entra in dispensa lo perdeva, e in lista
  // restava sotto «Senza reparto». Adesso si scrive subito sulla voce; il match
  // locale resta, così un salvataggio fallito non toglie niente a chi sta
  // sistemando la spesa.
  const persistMatch = useMutation({
    mutationFn: ({ item, ingredient }: { item: ShoppingItem; ingredient: Ingredient }) =>
      patchShoppingItem(item.id, { ingredient_id: ingredient.id }),
    onSuccess: (_saved, { item }) => {
      setMatchNotSaved((prev) => {
        const next = { ...prev };
        delete next[item.id];
        return next;
      });
      // la lista, qui e nella schermata «Lista», deve rimettere la voce nel suo
      // reparto: la cache dice ancora «Senza reparto»
      queryClient.invalidateQueries({ queryKey: ["shopping-list"] });
    },
    onError: (_error, { item, ingredient }) =>
      setMatchNotSaved((prev) => ({ ...prev, [item.id]: ingredient })),
  });

  function matchIngredient(item: ShoppingItem, ingredient: Ingredient) {
    setMatchedIngredient((prev) => ({ ...prev, [item.id]: ingredient }));
    persistMatch.mutate({ item, ingredient });
  }

  /** Un codice nuovo al catalogo, che si è deciso di usare: se Open Food Facts lo
   * conosce prima si chiede se è l'ingrediente della voce, se no il modulo. */
  function proceedWithNewCode(
    item: ShoppingItem,
    code: string,
    suggestion: ProductSuggestion | null
  ) {
    rememberUnlinkedCode(item, code);
    setBadCode(null);
    setScanningFor(null);
    if (suggestion) {
      setConfirmingFor({ item, barcode: code, suggestion });
    } else {
      setCreatingFor({ item, barcode: code, suggestion: null, lookedUp: "not_found" });
    }
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
              // sempre presente, mai assente: una riga senza scadenza scritta
              // manda `null`, non salta la chiave.
              //
              // `||` e non `??`, e la differenza è tutta qui: svuotare il campo
              // data (un Backspace su un segmento basta) lascia in `expiry` la
              // stringa vuota, e `''` non è una data — il backend risponde 422,
              // il messaggio dice «riprova», e il riprova ricostruisce lo stesso
              // corpo identico all'infinito. L'unica uscita sarebbe ricaricare,
              // buttando via tutte le risoluzioni. `PantryRow.commitExpiry` fa la
              // stessa cosa nello stesso modo: le due forme devono restare uguali.
              expires_on: expiry[itemId] || null,
              // sempre presente come la scadenza; `null` per lo sfuso e per ogni
              // prodotto che non è stato scelto a catalogo dopo un codice letto
              barcode: (resolution.kind === "product" && resolution.barcode) || null,
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
    // l'avviso parlava del codice di prima: con uno nuovo in volo non vale più
    onMutate: () => setBadCode(null),
    onSuccess: (result, { item, code }) => {
      const product = result.product;
      setMismatch(null);
      // un codice che ha già il suo prodotto non segue la voce altrove, neanche
      // quando quel prodotto è di un altro ingrediente: darlo a un prodotto nuovo
      // sarebbe un 409, e a uno scelto a catalogo un furto che il backend rifiuta.
      // Uno nuovo al catalogo lo ricorda proceedWithNewCode, quando si decide di
      // usarlo
      rememberUnlinkedCode(item, null);
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
      // un prodotto del catalogo si aggancia anche se la cifra di controllo non
      // torna: qualcuno l'ha già confermato con la confezione in mano
      if (product) {
        setResolved((prev) => ({ ...prev, [item.id]: { kind: "product", product } }));
        setScanningFor(null);
        return;
      }
      if (result.valid_checksum === false) {
        // S20: `1234` apriva la creazione di un prodotto sotto un codice che
        // nessuna confezione porta. Il codice resta nel campo, correggibile — un
        // codice letto dalla fotocamera ci arriva adesso — e «Usa questo codice lo
        // stesso» lascia andare avanti: i codici interni di negozio esistono.
        setBadCode({ item, code, suggestion: result.suggestion });
        setManualCode(code);
        return;
      }
      // Conosciuto da Open Food Facts ma non ancora in catalogo: prima la domanda,
      // poi il modulo precompilato. Ignoto anche lì, o servizio giù: il modulo,
      // stavolta vuoto — mai un muro.
      proceedWithNewCode(item, code, result.suggestion);
    },
    // il codice è stato letto anche se il lookup no: la via diretta lo porta già
    // al modulo («Crea il prodotto a mano» qui sotto), il catalogo deve fare lo
    // stesso. Se poi risultasse di un altro prodotto, il backend non lo sposta
    onError: (_error, { item, code }) => rememberUnlinkedCode(item, code),
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
    setConfirmingFor(null);
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
    setBadCode(null);
    setConfirmingFor(null);
    setScanningFor(item);
  }

  function createByHand(item: ShoppingItem, barcode: string, lookedUp?: "failed") {
    setCreatingFor({ item, barcode, suggestion: null, lookedUp });
    setConfirmingFor(null);
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
                  onMatched={(ingredient) => matchIngredient(item, ingredient)}
                />
              )}

              {/* accanto alla voce, e non un muro: la voce resta sistemabile dal
                  match locale, e l'abbinamento si può riprovare a scrivere */}
              {matchNotSaved[item.id] && (
                <div className="flex flex-col items-start gap-2">
                  <Alert>
                    Non sono riuscito a ricordare l'abbinamento in lista: la voce si sistema lo
                    stesso, ma se oggi non la metti in dispensa andrà rifatto.
                  </Alert>
                  <button
                    type="button"
                    onClick={() =>
                      persistMatch.mutate({ item, ingredient: matchNotSaved[item.id] })
                    }
                    disabled={persistMatch.isPending}
                    className={buttonClasses("secondary")}
                  >
                    Riprova<span className="sr-only"> ad abbinare {item.raw_text}</span>
                  </button>
                </div>
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

              {/* Dietro un tocco, sempre: indipendente dalla risoluzione (resta
                  raggiungibile anche a riga già confermata, come nel secondo test)
                  perché la data riguarda il lotto che entra in dispensa, non il
                  come è stato scelto il prodotto. */}
              {openExpiryFor[item.id] ? (
                <div>
                  <label htmlFor={`expiry-${item.id}`} className="sr-only">
                    Scadenza di {item.raw_text}
                  </label>
                  <input
                    id={`expiry-${item.id}`}
                    type="date"
                    max={EXPIRY_INPUT_MAX}
                    value={expiry[item.id] ?? ""}
                    onChange={(e) =>
                      setExpiry((prev) => ({ ...prev, [item.id]: e.target.value }))
                    }
                  />
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() =>
                    setOpenExpiryFor((prev) => ({ ...prev, [item.id]: true }))
                  }
                  // come in dispensa: si allarga il bersaglio, non il disegno (44px di
                  // riquadro, ritolti dal flusso dal margine negativo, così la voce non
                  // si allunga sullo schermo più fitto dell'app). Qui però la sporgenza
                  // è sbilanciata in basso: sopra, a soli 8px, ci sono i tre pulsanti
                  // della risoluzione, e un bersaglio simmetrico da 44px si sovrapporrebbe
                  // al loro; sotto c'è solo il fondo della voce, cioè vuoto.
                  className="-mt-2 -mb-5 self-start pt-2 pb-5 text-xs font-medium text-ink-faint"
                >
                  + scadenza<span className="sr-only"> per {item.raw_text}</span>
                </button>
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
          {/* la cifra di controllo non torna: il codice sta nel campo qui sopra,
              da correggere e rileggere con Invio, oppure da usare così com'è */}
          {badCode && badCode.item.id === scanningFor.id && (
            <div className="flex flex-col items-start gap-2">
              <Alert>Questo codice non torna: ricontrollalo.</Alert>
              <button
                type="button"
                onClick={() =>
                  proceedWithNewCode(badCode.item, badCode.code, badCode.suggestion)
                }
                className={buttonClasses("secondary")}
              >
                Usa questo codice lo stesso
              </button>
            </div>
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
                onClick={() => createByHand(failedLookup.item, failedLookup.code, "failed")}
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
          // il codice letto un attimo prima segue entrambe le uscite che danno un
          // prodotto (S8): senza, la prossima scansione dello stesso codice non
          // trovava niente e si ricominciava da capo
          onPicked={(product) => {
            setResolved((prev) => ({
              ...prev,
              [searchingFor.id]: {
                kind: "product",
                product,
                barcode: unlinkedCode[searchingFor.id],
              },
            }));
            setSearchingFor(null);
          }}
          onCreateByHand={() => createByHand(searchingFor, unlinkedCode[searchingFor.id] ?? "")}
          onCancel={() => setSearchingFor(null)}
        />
      )}

      {confirmingFor && effectiveIngredientId(confirmingFor.item) && (
        <div className="mt-4">
          <OffSuggestionQuestion
            ingredientName={effectiveIngredientName(confirmingFor.item)}
            suggestion={confirmingFor.suggestion}
            onYes={() => {
              setCreatingFor({ ...confirmingFor, lookedUp: undefined });
              setConfirmingFor(null);
            }}
            onNo={() => {
              // Indietro a prima del codice: i pulsanti della voce sono ancora là,
              // perché non c'è nessuna risoluzione. Il codice non segue la voce —
              // è di un'altra cosa, e dal catalogo finirebbe al prodotto sbagliato
              rememberUnlinkedCode(confirmingFor.item, null);
              setConfirmingFor(null);
            }}
          />
        </div>
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
            lookedUp={creatingFor.lookedUp}
            isNonFood={effectiveKind(creatingFor.item) === "non_food"}
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

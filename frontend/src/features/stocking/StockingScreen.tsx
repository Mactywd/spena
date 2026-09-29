import { useCallback, useRef, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { fetchShoppingList, patchShoppingItem } from "../shopping-list/api";
import { groupForDisplay } from "../shopping-list/listView";
import { CatalogSearchPanel } from "./CatalogSearchPanel";
import { CustomProductForm } from "./CustomProductForm";
import type { ProductSuggestion } from "./CustomProductForm";
import { MatchPanel } from "./MatchPanel";
import { OffSuggestionQuestion } from "./OffSuggestionQuestion";
import { ScannerPanel } from "./ScannerPanel";
import { StockingRow } from "./StockingRow";
import { stockItems } from "./api";
import {
  stockEntries,
  stockNotice,
  type FocusTarget,
  type PanelTrigger,
  type Resolution,
  type StockEntry,
} from "./stockingView";
import { ApiError } from "../../api/client";
import { Button } from "../../components/ui/Button";
import { EmptyState } from "../../components/ui/EmptyState";
import { ErrorState } from "../../components/ui/ErrorState";
import { Screen } from "../../components/ui/Screen";
import { Section } from "../../components/ui/Section";
import { buttonClasses } from "../../components/ui/buttonClasses";
import { IconPackageImport } from "../../components/ui/icons";
import { useNotice } from "../../components/ui/noticeContext";
import type { Ingredient, ShoppingItem } from "../../domain/types";

/** Il pannello aperto sotto una voce: uno alla volta, in un solo stato (T3 Consegna 3).
 * Prima erano quattro stati sparsi, e due pannelli potevano stare aperti insieme sulla
 * stessa voce — dicendo due cose diverse su cosa stava per entrare in dispensa. */
type Panel =
  | { itemId: string; kind: "scanner" }
  | { itemId: string; kind: "catalog" }
  | { itemId: string; kind: "match" }
  // il codice nuovo al catalogo che Open Food Facts conosce: prima del modulo, la
  // domanda (S20)
  | { itemId: string; kind: "off-question"; barcode: string; suggestion: ProductSuggestion }
  | {
      itemId: string;
      kind: "product-form";
      /** Chi l'ha aperto: lì torna il fuoco, annullando. */
      trigger: PanelTrigger;
      barcode: string;
      suggestion: ProductSuggestion | null;
      lookedUp?: "not_found" | "failed";
    };

/** Il pulsante della voce che aveva aperto il pannello. */
function triggerOf(panel: Panel): PanelTrigger {
  if (panel.kind === "off-question") return "scanner";
  if (panel.kind === "product-form") return panel.trigger;
  return panel.kind;
}

/** Il registro senza la chiave; lo stesso registro se non c'era. */
function without<T>(record: Record<string, T>, key: string): Record<string, T> {
  if (!(key in record)) return record;
  const next = { ...record };
  delete next[key];
  return next;
}

/** Perché la sistemazione è fallita, in una frase che dice cosa fare.
 *
 * «Riprova» da solo era un vicolo cieco su due delle tre cause: la sistemazione è
 * tutto-o-niente, quindi lo stesso corpo rimandato dà lo stesso errore per sempre.
 * Riprovare è l'azione giusta solo quando la causa è passeggera (rete, backend
 * giù); le altre due si risolvono cambiando una scelta o rileggendo la lista, e
 * vanno nominate. Il 409 non dovrebbe più essere raggiungibile dall'interfaccia
 * (vedi la guardia in ScannerPanel e il filtro di CatalogSearchPanel): se arriva, la
 * via d'uscita è «Cambia» sulla voce sbagliata.
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

/** «Sistema la spesa» (spec T3 §4.3): le voci nel carrello, per reparto come in Lista,
 * ciascuna da far entrare in dispensa col codice, dal catalogo o sfusa. */
export function StockingScreen() {
  const navigate = useNavigate();
  const notice = useNotice();
  const queryClient = useQueryClient();
  const { data, isLoading, isError, isFetching, refetch } = useQuery({
    queryKey: ["shopping-list", "checked"],
    queryFn: () => fetchShoppingList(["checked"]),
  });
  // un caricamento fallito non è una lista vuota; ma se uno era già riuscito, React
  // Query ne tiene i dati anche quando il successivo fallisce, e quelli restano a video
  // sotto l'errore. `loaded` distingue i due casi, come in Lista e in Dispensa
  const loaded = data !== undefined;
  const items = data ?? [];

  const [resolved, setResolved] = useState<Record<string, Resolution>>({});
  // La scadenza scritta per voce. Una chiave presente è un campo aperto — anche vuoto,
  // appena toccato «+ scadenza» — e la ✕ la toglie. Sta qui e non nella riga: la riga
  // sparisce mentre un'altra voce ha il pannello aperto (decisione 1), e la data scritta
  // non deve sparire con lei.
  const [expiry, setExpiry] = useState<Record<string, string>>({});
  // voci senza ingredient_id, abbinate a mano in questo schermo
  const [matchedIngredient, setMatchedIngredient] = useState<Record<string, Ingredient>>({});
  // S19: l'abbinamento fatto qui e non scritto sulla voce, con l'ingrediente per
  // riprovare. La voce resta sistemabile lo stesso, dal match locale
  const [matchNotSaved, setMatchNotSaved] = useState<Record<string, Ingredient>>({});
  // Il codice letto per una voce e rimasto senza prodotto — ignoto al catalogo, o
  // lookup fallito — indicizzato come `resolved` (S8). Chi poi chiude il modulo e passa
  // dal catalogo, lì crea il prodotto a mano o ne sceglie uno esistente: senza questo il
  // codice si perdeva, e la scansione successiva non trovava niente. Lo sfuso non lo
  // legge: non c'è un prodotto a cui darlo.
  const [unlinkedCode, setUnlinkedCode] = useState<Record<string, string>>({});
  const [panel, setPanel] = useState<Panel | null>(null);
  // Il pannello aperto adesso, per chi arriva in ritardo. Le mutazioni dei pannelli (il
  // lookup del codice, la creazione dell'ingrediente o del prodotto) chiamano i loro
  // `on…` anche a pannello già chiuso — react-query li tiene — e con la chiusura di un
  // render passato, dove quel pannello era ancora aperto. Un esito vale solo se il suo
  // pannello è ancora quello aperto (lo stesso oggetto: riaperto è un altro): dopo
  // «Annulla», o con un'altra voce davanti, non sceglie niente e non chiude niente.
  const openPanel = useRef<Panel | null>(null);
  // dove rimettere il fuoco quando la riga rinasce (vedi StockingRow)
  const [returnFocus, setReturnFocus] = useState<{ itemId: string; target: FocusTarget } | null>(
    null
  );
  // La voce appena abbinata, finché la rilettura non la rimette nel suo reparto (S19).
  // Il fuoco sulla prima icona (decisione 18) non sopravvive al trasloco: la riga lascia
  // la sezione «Senza reparto» e rinasce in un'altra, e il pulsante che lo aveva sparisce
  // con la vecchia. La richiesta aspetta la voce riletta, che porta il suo ingrediente,
  // e scatta dove la riga rinasce; la riga non ruba il fuoco a chi è già altrove.
  const [refocusAfterMatch, setRefocusAfterMatch] = useState<string | null>(null);
  const clearReturnFocus = useCallback(() => {
    setReturnFocus(null);
    setRefocusAfterMatch(null);
  }, []);

  function setOpen(next: Panel | null) {
    openPanel.current = next;
    setPanel(next);
  }

  function isOpen(which: Panel): boolean {
    return openPanel.current === which;
  }

  function ingredientOf(item: ShoppingItem): string | null {
    return item.ingredient_id ?? matchedIngredient[item.id]?.id ?? null;
  }

  // Lo stesso ragionamento di `ingredientOf`: la voce può avere il suo ingrediente dalla
  // lista, oppure averlo appena abbinato qui dentro. `null` vuol dire "non lo so" e fa
  // mostrare i campi nutrienti come per un alimentare; non è raggiungibile dove si usa,
  // perché il modulo si apre solo se `ingredientOf(item)` c'è, e reparto e
  // identificativo arrivano sempre insieme dalla stessa fonte.
  function kindOf(item: ShoppingItem): "food" | "non_food" | null {
    return item.ingredient_kind ?? matchedIngredient[item.id]?.kind ?? null;
  }

  // lo stesso nome canonico nei due casi: `ingredient_name` del backend è
  // `ingredient.name`, non `display_name`
  function ingredientNameOf(item: ShoppingItem): string {
    return item.ingredient_name ?? matchedIngredient[item.id]?.name ?? item.raw_text;
  }

  function rememberUnlinkedCode(item: ShoppingItem, code: string | null) {
    setUnlinkedCode((prev) => (code ? { ...prev, [item.id]: code } : without(prev, item.id)));
  }

  // S19: l'abbinamento viveva solo nello stato fino a «Metti in dispensa». Una voce che
  // oggi non entra in dispensa lo perdeva, e in lista restava sotto «Senza reparto».
  // Adesso si scrive subito sulla voce; il match locale resta, così un salvataggio
  // fallito non toglie niente a chi sta sistemando la spesa.
  const persistMatch = useMutation({
    mutationFn: ({ item, ingredient }: { item: ShoppingItem; ingredient: Ingredient }) =>
      patchShoppingItem(item.id, { ingredient_id: ingredient.id }),
    onSuccess: (_saved, { item }) => {
      setMatchNotSaved((prev) => without(prev, item.id));
      setRefocusAfterMatch(item.id);
      // la lista, qui e nella schermata «Lista», deve rimettere la voce nel suo reparto:
      // la cache dice ancora «Senza reparto»
      queryClient.invalidateQueries({ queryKey: ["shopping-list"] });
    },
    onError: (_error, { item, ingredient }) =>
      setMatchNotSaved((prev) => ({ ...prev, [item.id]: ingredient })),
  });

  const stock = useMutation({
    mutationFn: ({ sent }: { sent: StockEntry[]; checked: number }) => stockItems(sent),
    onSuccess: (_created, { sent, checked }) => {
      // la lista della spesa tiene in cache le stesse voci: senza invalidare questo
      // prefisso, tornando a "Lista" le voci appena sistemate restano spuntate
      queryClient.invalidateQueries({ queryKey: ["shopping-list"] });
      // prima di cambiare schermata: l'avviso vive in NoticeProvider, sopra il router
      // (App.tsx), e arriva in Dispensa (T4)
      notice({ text: stockNotice(sent.length, checked) });
      navigate("/dispensa");
    },
  });

  /** Apre un pannello. La vista cambia forma e la riga rinasce: il fuoco torna al
   * pulsante che l'ha aperto, o cadrebbe sul `body`. Il selettore di «Abbina» il fuoco
   * lo prende da sé. */
  function show(next: Panel) {
    setOpen(next);
    // chi apre un pannello ha già il fuoco altrove: l'abbinamento in attesa di
    // rilettura non deve riprenderselo quando la vista torna intera
    setRefocusAfterMatch(null);
    if (next.kind !== "match") setReturnFocus({ itemId: next.itemId, target: triggerOf(next) });
  }

  function openPanelFor(item: ShoppingItem, trigger: PanelTrigger) {
    if (trigger === "scanner") show({ itemId: item.id, kind: "scanner" });
    else if (trigger === "catalog") show({ itemId: item.id, kind: "catalog" });
    else show({ itemId: item.id, kind: "match" });
  }

  /** Chiude il pannello senza scegliere: tutto torna a video, e il fuoco torna al
   * pulsante che l'aveva aperto (decisione 1). */
  function closePanel(which: Panel) {
    if (!isOpen(which)) return;
    setReturnFocus({ itemId: which.itemId, target: triggerOf(which) });
    setOpen(null);
  }

  /** Una scelta fatta: chiude il pannello di questa voce, se c'è. Le tre icone lasciano
   * il posto a «Cambia», e il fuoco va lì. */
  function resolve(item: ShoppingItem, resolution: Resolution) {
    setResolved((prev) => ({ ...prev, [item.id]: resolution }));
    if (openPanel.current?.itemId === item.id) setOpen(null);
    setReturnFocus({ itemId: item.id, target: "change" });
  }

  /** La scelta arrivata da un pannello: vale solo se quel pannello è ancora aperto. */
  function resolveFrom(which: Panel, item: ShoppingItem, resolution: Resolution) {
    if (isOpen(which)) resolve(item, resolution);
  }

  /** Disfa la scelta di una voce, lasciando intatte le altre. Azzera anche l'errore della
   * sistemazione, che parlava di un tentativo fatto su scelte che da adesso non sono più
   * quelle. */
  function changeResolution(item: ShoppingItem) {
    setResolved((prev) => without(prev, item.id));
    stock.reset();
    setReturnFocus({ itemId: item.id, target: "scanner" });
  }

  function matchIngredient(which: Panel, item: ShoppingItem, ingredient: Ingredient) {
    // un ingrediente creato dopo «Annulla» resta in anagrafica, e il selettore lo
    // ritrova: la voce però non si abbina da sola a cose chiuse
    if (!isOpen(which)) return;
    setMatchedIngredient((prev) => ({ ...prev, [item.id]: ingredient }));
    persistMatch.mutate({ item, ingredient });
    setOpen(null);
    // ora la voce ha le tre icone: il fuoco va alla prima (decisione 18)
    setReturnFocus({ itemId: item.id, target: "scanner" });
  }

  /** Un codice nuovo al catalogo, che si è deciso di usare: se Open Food Facts lo
   * conosce prima si chiede se è l'ingrediente della voce, se no il modulo. */
  function proceedWithNewCode(
    which: Panel,
    item: ShoppingItem,
    code: string,
    suggestion: ProductSuggestion | null
  ) {
    if (!isOpen(which)) return;
    rememberUnlinkedCode(item, code);
    show(
      suggestion
        ? { itemId: item.id, kind: "off-question", barcode: code, suggestion }
        : {
            itemId: item.id,
            kind: "product-form",
            trigger: "scanner",
            barcode: code,
            suggestion: null,
            lookedUp: "not_found",
          }
    );
  }

  /** «Crea il prodotto a mano», dallo scanner o dal catalogo. Il codice letto prima per
   * questa voce segue anche questa uscita (S8), da qualunque pannello si arrivi. */
  function openProductForm(
    item: ShoppingItem,
    trigger: PanelTrigger,
    barcode: string,
    lookedUp?: "failed"
  ) {
    show({
      itemId: item.id,
      kind: "product-form",
      trigger,
      barcode: barcode || unlinkedCode[item.id] || "",
      suggestion: null,
      lookedUp,
    });
  }

  // una fonte per il corpo della richiesta e per il numero sul pulsante (decisione 4)
  const entries = stockEntries(items, resolved, ingredientOf, expiry);

  function submitStock() {
    // la guardia al posto di `disabled`: il pulsante resta dov'è il fuoco
    if (entries.length === 0 || stock.isPending) return;
    stock.mutate({ sent: entries, checked: items.length });
  }

  function renderPanel(item: ShoppingItem, open: Panel): ReactNode {
    if (open.kind === "match") {
      return (
        <MatchPanel
          key={item.id}
          item={item}
          onMatched={(ingredient) => matchIngredient(open, item, ingredient)}
          onCancel={() => closePanel(open)}
        />
      );
    }
    // ogni altro pannello lega un prodotto a un ingrediente: una voce senza non ha le
    // tre icone, e un pannello rimasto aperto su di lei non ha niente da mostrare. Lo
    // scanner in particolare confronta il prodotto trovato con questo ingrediente (la
    // guardia del 409): senza, non ha niente con cui confrontarlo
    const ingredientId = ingredientOf(item);
    if (!ingredientId) return null;
    if (open.kind === "scanner") {
      return (
        <ScannerPanel
          // un pannello per voce: il codice scritto a mano per un'altra voce non
          // sopravvive nel campo (S8)
          key={item.id}
          item={item}
          ingredientId={ingredientId}
          onProduct={(product) => resolveFrom(open, item, { kind: "product", product })}
          onNewCode={(code, suggestion) => proceedWithNewCode(open, item, code, suggestion)}
          onUnlinkedCode={(code) => rememberUnlinkedCode(item, code)}
          onCreateByHand={(code, lookedUp) => openProductForm(item, "scanner", code, lookedUp)}
          onCancel={() => closePanel(open)}
        />
      );
    }
    if (open.kind === "catalog") {
      return (
        <CatalogSearchPanel
          key={item.id}
          itemLabel={item.raw_text}
          ingredientId={ingredientId}
          // il codice letto un attimo prima segue entrambe le uscite che danno un
          // prodotto (S8): senza, la prossima scansione dello stesso codice non trovava
          // niente e si ricominciava da capo
          onPicked={(product) =>
            resolveFrom(open, item, { kind: "product", product, barcode: unlinkedCode[item.id] })
          }
          onCreateByHand={() => openProductForm(item, "catalog", "")}
          onCancel={() => closePanel(open)}
        />
      );
    }
    if (open.kind === "off-question") {
      return (
        <OffSuggestionQuestion
          ingredientName={ingredientNameOf(item)}
          suggestion={open.suggestion}
          onYes={() =>
            show({
              itemId: item.id,
              kind: "product-form",
              trigger: "scanner",
              barcode: open.barcode,
              suggestion: open.suggestion,
            })
          }
          onNo={() => {
            // indietro a prima del codice: le icone della voce sono ancora là. Il codice
            // non segue la voce — è di un'altra cosa, e dal catalogo finirebbe al
            // prodotto sbagliato
            rememberUnlinkedCode(item, null);
            closePanel(open);
          }}
        />
      );
    }
    return (
      <div className="rounded-card border border-line">
        <CustomProductForm
          // senza key React riusa l'istanza passando da una voce all'altra: i campi
          // restano quelli di prima mentre ingrediente e codice sono già i nuovi, e si
          // salva il prodotto sbagliato sotto l'ingrediente sbagliato, in silenzio
          key={`${item.id}:${open.barcode}`}
          ingredientId={ingredientId}
          itemLabel={item.raw_text}
          barcode={open.barcode}
          suggestion={open.suggestion}
          lookedUp={open.lookedUp}
          isNonFood={kindOf(item) === "non_food"}
          onCreated={(product) => resolveFrom(open, item, { kind: "product", product })}
          onCancel={() => closePanel(open)}
        />
      </div>
    );
  }

  /** Dove rimettere il fuoco in questa riga, quando rinasce. Una richiesta esplicita
   * vince sempre, anche se è per un'altra voce: gli effetti delle righe girano in ordine
   * di albero, e una voce abbinata che viene prima prenderebbe il fuoco dal `body`
   * lasciando senza la riga che l'aveva chiesto. La richiesta dopo l'abbinamento vale
   * solo per la voce riletta col suo ingrediente: prima, la riga è ancora quella di
   * «Senza reparto» che sta per sparire. */
  function returnFocusFor(item: ShoppingItem): FocusTarget | null {
    if (returnFocus) return returnFocus.itemId === item.id ? returnFocus.target : null;
    if (refocusAfterMatch === item.id && item.ingredient_id) {
      return resolved[item.id] ? "change" : "scanner";
    }
    return null;
  }

  function renderRow(item: ShoppingItem) {
    return (
      <StockingRow
        key={item.id}
        item={item}
        resolution={resolved[item.id]}
        ingredientId={ingredientOf(item)}
        expiry={expiry[item.id]}
        onExpiry={(value) =>
          setExpiry((prev) =>
            value === undefined ? without(prev, item.id) : { ...prev, [item.id]: value }
          )
        }
        matchNotSaved={item.id in matchNotSaved}
        retryingMatch={persistMatch.isPending}
        onRetryMatch={() => persistMatch.mutate({ item, ingredient: matchNotSaved[item.id] })}
        focused={panel?.itemId === item.id}
        returnFocusTo={returnFocusFor(item)}
        onFocusReturned={clearReturnFocus}
        onOpen={(trigger) => openPanelFor(item, trigger)}
        onLoose={() => resolve(item, { kind: "loose" })}
        onChange={() => changeResolution(item)}
      >
        {panel?.itemId === item.id ? renderPanel(item, panel) : null}
      </StockingRow>
    );
  }

  // la voce del pannello aperto; se è sparita da una rilettura, la vista torna intera
  const focusItem = panel ? items.find((item) => item.id === panel.itemId) : undefined;

  return (
    <Screen title="Sistema la spesa" back={{ to: "/lista", label: "Lista" }}>
      <div className="flex flex-col gap-3">
        {isLoading && <p className="text-ink-soft">Carico…</p>}

        {/* un caricamento fallito non è una lista vuota: dire "non hai spuntato niente"
            a chi è tornato dalla spesa con le borse in mano è una bugia */}
        {isError && (
          <ErrorState
            message={
              loaded
                ? "Non sono riuscito ad aggiornare la spesa da sistemare. Quella qui sotto è dell'ultimo caricamento."
                : "Non sono riuscito a caricare la spesa da sistemare. La lista non è vuota: non l'ho letta."
            }
            onRetry={() => void refetch()}
            retrying={isFetching}
          />
        )}

        {loaded && items.length === 0 && (
          <EmptyState
            title="Niente da sistemare"
            body="Qui arriva quel che spunti in Lista mentre fai la spesa."
            action={
              <Link to="/lista" className={buttonClasses("primary")}>
                Vai alla Lista
              </Link>
            }
          />
        )}

        {focusItem ? (
          // decisione 1 (Mattia): col pannello aperto restano a video solo la sua voce e
          // il pannello. Le scelte fatte sulle altre sono indicizzate per voce, e restano
          <div className="rounded-2xl bg-card px-3 py-2">
            <ul>{renderRow(focusItem)}</ul>
          </div>
        ) : (
          items.length > 0 && (
            <>
              {groupForDisplay(items).map(([category, rows]) => (
                <Section key={category ?? "senza-reparto"} category={category} count={rows.length}>
                  <ul>{rows.map((item) => renderRow(item))}</ul>
                </Section>
              ))}

              <div className="flex flex-col gap-2 pt-1">
                {stock.isError && (
                  <div className="flex flex-col items-start gap-2">
                    <p role="alert" className="text-sm text-danger">
                      {stockFailureMessage(stock.error)}
                    </p>
                    {/* un 404 è l'unico caso in cui riprovare così com'è non può
                        riuscire: la lista va riletta. Le scelte sono indicizzate per id
                        di voce, quindi sopravvivono alla rilettura — e quella della voce
                        sparita resta fuori dal corpo da sé */}
                    {stock.error instanceof ApiError && stock.error.status === 404 && (
                      <Button
                        onClick={() => {
                          // anche l'errore va via: acceso dopo la rilettura direbbe che
                          // c'è ancora un guasto su uno schermo già rimesso in sesto
                          stock.reset();
                          void refetch();
                        }}
                      >
                        Rileggi la spesa da sistemare
                      </Button>
                    )}
                  </div>
                )}
                {/* `aria-disabled` e non `disabled`: mentre la sistemazione è in volo il
                    fuoco resta qui. Il numero è quello delle voci che partono davvero */}
                <button
                  type="button"
                  onClick={submitStock}
                  aria-disabled={entries.length === 0 || stock.isPending || undefined}
                  className={`${buttonClasses("primary", "block")} aria-disabled:opacity-40`}
                >
                  <IconPackageImport aria-hidden="true" className="size-[1.1em]" stroke={1.8} />
                  {entries.length > 0 ? `Metti in dispensa ${entries.length}` : "Metti in dispensa"}
                </button>
                {/* un pulsante spento e muto non si spiega da sé (dal giro) */}
                {entries.length === 0 && (
                  <p className="text-xs text-ink-soft">
                    Scegli come entra almeno una voce: codice, catalogo o sfuso.
                  </p>
                )}
              </div>
            </>
          )
        )}
      </div>
    </Screen>
  );
}

import { useCallback, useRef, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { addShoppingItem, fetchShoppingList, patchShoppingItem } from "../shopping-list/api";
import { groupForDisplay } from "../shopping-list/listView";
import { IngredientChooser } from "./IngredientChooser";
import { MatchPanel } from "./MatchPanel";
import { PackageRow } from "./PackageRow";
import { ProductResolver } from "./ProductResolver";
import { StockingRow } from "./StockingRow";
import { stockItems } from "./api";
import {
  itemsLeft,
  stockEntries,
  stockNotice,
  type FocusTarget,
  type PanelTrigger,
  type Resolution,
  type StockEntry,
} from "./stockingView";
import { ApiError } from "../../api/client";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { EmptyState } from "../../components/ui/EmptyState";
import { ErrorState } from "../../components/ui/ErrorState";
import { Screen } from "../../components/ui/Screen";
import { Section } from "../../components/ui/Section";
import { buttonClasses } from "../../components/ui/buttonClasses";
import { IconPackageImport, IconPlus } from "../../components/ui/icons";
import { useNotice } from "../../components/ui/noticeContext";
import type { Ingredient, ShoppingItem } from "../../domain/types";

/** «Abbina», sotto una voce senza ingrediente: è della voce. */
type MatchPanelState = { itemId: string; kind: "match" };

/** Il codice, il catalogo e quel che ne segue: sono di una confezione, e li dirige
 * `ProductResolver` (S3). La prima confezione di una voce ha la chiave della voce
 * (`packageKey === itemId`). `serial` distingue due aperture: riaperto è un altro
 * pannello, e il suo resolver rinasce. */
type ResolverPanelState = {
  itemId: string;
  kind: "resolver";
  packageKey: string;
  start: "scanner" | "catalog";
  serial: number;
};

/** Il pannello aperto: uno alla volta, in un solo stato (T3 Consegna 3). Prima erano
 * quattro stati sparsi, e due pannelli potevano stare aperti insieme sulla stessa voce
 * — dicendo due cose diverse su cosa stava per entrare in dispensa. */
type Panel = MatchPanelState | ResolverPanelState;

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
    "Se insiste, è il server che non risponde: le conferme restano su questo schermo."
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

  // Le scelte, le scadenze e i codici sono per confezione (S3 §10.2): la prima
  // confezione di una voce ha la chiave della voce, come prima che ce ne fossero altre.
  const [resolved, setResolved] = useState<Record<string, Resolution>>({});
  // La scadenza scritta per confezione. Una chiave presente è un campo aperto — anche
  // vuoto, appena toccato «+ scadenza» — e la ✕ la toglie. Sta qui e non nella riga: la
  // riga sparisce mentre un'altra voce ha il pannello aperto (decisione 1), e la data
  // scritta non deve sparire con lei.
  const [expiry, setExpiry] = useState<Record<string, string>>({});
  // voci senza ingredient_id, abbinate a mano in questo schermo
  const [matchedIngredient, setMatchedIngredient] = useState<Record<string, Ingredient>>({});
  // S19: l'abbinamento fatto qui e non scritto sulla voce, con l'ingrediente per
  // riprovare. La voce resta sistemabile lo stesso, dal match locale
  const [matchNotSaved, setMatchNotSaved] = useState<Record<string, Ingredient>>({});
  // Il codice letto per una confezione e rimasto senza prodotto (S8). Lo tiene lo
  // schermo perché sopravviva al pannello che si chiude: chi chiude il modulo e passa
  // dal catalogo lo ritrova. Quando seguirlo lo decide ProductResolver.
  const [rememberedCode, setRememberedCode] = useState<Record<string, string>>({});
  const [panel, setPanel] = useState<Panel | null>(null);
  // Il pannello aperto adesso, per chi arriva in ritardo: la creazione di un
  // ingrediente in «Abbina» chiama i suoi `on…` anche a pannello chiuso. Un esito vale
  // solo se il suo pannello è ancora quello aperto (lo stesso oggetto: riaperto è un
  // altro). I pannelli di una confezione hanno la stessa guardia dentro ProductResolver
  const openPanel = useRef<Panel | null>(null);
  const panelSerial = useRef(0);
  // Le confezioni in più di ogni voce (S3 §10.2), in ordine; la prima ha la chiave della
  // voce e non sta qui. Chiavi mai riusate: togliendone una, la scelta di un'altra non
  // le passa sopra
  const [extraPackages, setExtraPackages] = useState<Record<string, string[]>>({});
  const packageSerial = useRef(0);
  // dove rimettere il fuoco quando la riga di una confezione rinasce (vedi StockingRow)
  const [returnFocus, setReturnFocus] = useState<{ key: string; target: FocusTarget } | null>(
    null
  );
  // La voce appena abbinata, finché la rilettura non la rimette nel suo reparto (S19).
  // Il fuoco sulla prima icona (decisione 18) non sopravvive al trasloco: la riga lascia
  // la sezione «Senza reparto» e rinasce in un'altra, e il pulsante che lo aveva sparisce
  // con la vecchia. La richiesta aspetta la voce riletta, che porta il suo ingrediente,
  // e scatta dove la riga rinasce; la riga non ruba il fuoco a chi è già altrove.
  // Lo usa anche «Articolo aggiuntivo»: la voce nuova arriva con la rilettura, e il fuoco
  // la aspetta allo stesso modo.
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
    mutationFn: ({ sent }: { sent: StockEntry[]; left: number }) => stockItems(sent),
    onSuccess: (_created, { sent, left }) => {
      // la lista della spesa tiene in cache le stesse voci: senza invalidare questo
      // prefisso, tornando a "Lista" le voci appena sistemate restano spuntate
      queryClient.invalidateQueries({ queryKey: ["shopping-list"] });
      // prima di cambiare schermata: l'avviso vive in NoticeProvider, sopra il router
      // (App.tsx), e arriva in Dispensa (T4)
      notice({ text: stockNotice(sent.length, left) });
      navigate("/dispensa");
    },
  });

  // «Articolo aggiuntivo» (S3 §10.1, forma a): una cosa comprata che in lista non
  // c'era. Diventa una voce di lista nata spuntata, con le rotte di oggi, e si sistema
  // qui come le altre: la sistemazione resta tutto-o-niente, e la rotta `stock` non cambia
  const [extraOpen, setExtraOpen] = useState(false);
  const addExtra = useMutation({
    mutationFn: async (ingredient: Ingredient) => {
      // il testo della voce è il nome dell'ingrediente, come se l'avessi scritto. Un
      // ingrediente già in lista non si doppia (S18): il backend risponde con la voce che
      // c'era — da comprare, la si spunta, perché è stata comprata (A, deciso da Mattia il 2026-10-09);
      // già spuntata, è già qui
      const added = await addShoppingItem(ingredient.display_name, ingredient.id);
      if (added.status === "checked") return added;
      return patchShoppingItem(added.id, { status: "checked" });
    },
    onSuccess: (item) => {
      setExtraOpen(false);
      // il fuoco va alla prima icona della voce quando la lista riletta la porta: lo
      // stesso percorso di un abbinamento (S19)
      setRefocusAfterMatch(item.id);
      return queryClient.invalidateQueries({ queryKey: ["shopping-list"] });
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
    if (next.kind === "resolver") setReturnFocus({ key: next.packageKey, target: next.start });
  }

  function openPanelFor(item: ShoppingItem, packageKey: string, trigger: PanelTrigger) {
    if (trigger === "match") {
      show({ itemId: item.id, kind: "match" });
      return;
    }
    panelSerial.current += 1;
    show({ itemId: item.id, kind: "resolver", packageKey, start: trigger, serial: panelSerial.current });
  }

  /** Chiude il pannello senza scegliere: tutto torna a video, e il fuoco torna al
   * pulsante che l'aveva aperto (decisione 1). */
  function closePanel(which: Panel, trigger: PanelTrigger) {
    if (!isOpen(which)) return;
    setReturnFocus({ key: which.kind === "resolver" ? which.packageKey : which.itemId, target: trigger });
    setOpen(null);
  }

  /** Una scelta fatta: chiude il pannello di questa confezione, se c'è. Le tre icone
   * lasciano il posto a «Cambia», e il fuoco va lì. */
  function resolve(packageKey: string, resolution: Resolution) {
    setResolved((prev) => ({ ...prev, [packageKey]: resolution }));
    const open = openPanel.current;
    if (open?.kind === "resolver" && open.packageKey === packageKey) setOpen(null);
    setReturnFocus({ key: packageKey, target: "change" });
  }

  /** Disfa la scelta di una confezione, lasciando intatte le altre. Azzera anche
   * l'errore della sistemazione, che parlava di un tentativo fatto su scelte che da
   * adesso non sono più quelle. */
  function changeResolution(packageKey: string) {
    setResolved((prev) => without(prev, packageKey));
    stock.reset();
    setReturnFocus({ key: packageKey, target: "scanner" });
  }

  function matchIngredient(which: MatchPanelState, item: ShoppingItem, ingredient: Ingredient) {
    // un ingrediente creato dopo «Annulla» resta in anagrafica, e il selettore lo
    // ritrova: la voce però non si abbina da sola a cose chiuse
    if (!isOpen(which)) return;
    setMatchedIngredient((prev) => ({ ...prev, [item.id]: ingredient }));
    persistMatch.mutate({ item, ingredient });
    setOpen(null);
    // ora la voce ha le tre icone: il fuoco va alla prima (decisione 18)
    setReturnFocus({ key: item.id, target: "scanner" });
  }

  function writeExpiry(packageKey: string, value: string | undefined) {
    setExpiry((prev) =>
      value === undefined ? without(prev, packageKey) : { ...prev, [packageKey]: value }
    );
  }

  function packagesOf(item: ShoppingItem): string[] {
    return [item.id, ...(extraPackages[item.id] ?? [])];
  }

  /** «+ un'altra confezione»: una riga nuova sotto la voce, con le sue tre strade; il
   * fuoco va alla prima. */
  function addPackage(item: ShoppingItem) {
    packageSerial.current += 1;
    const key = `${item.id}+${packageSerial.current}`;
    setExtraPackages((prev) => ({ ...prev, [item.id]: [...(prev[item.id] ?? []), key] }));
    stock.reset();
    setReturnFocus({ key, target: "scanner" });
  }

  /** La ✕ di una confezione in più: via lei, la sua scelta, la sua data, il suo codice,
   * e il suo pannello se era aperto. Il fuoco torna alla voce. */
  function removePackage(item: ShoppingItem, key: string) {
    setExtraPackages((prev) => ({
      ...prev,
      [item.id]: (prev[item.id] ?? []).filter((other) => other !== key),
    }));
    setResolved((prev) => without(prev, key));
    setExpiry((prev) => without(prev, key));
    setRememberedCode((prev) => without(prev, key));
    const open = openPanel.current;
    if (open?.kind === "resolver" && open.packageKey === key) setOpen(null);
    stock.reset();
    setReturnFocus({ key: item.id, target: resolved[item.id] ? "change" : "scanner" });
  }

  // una fonte per il corpo della richiesta e per il numero sul pulsante (decisione 4)
  const entries = stockEntries(items, resolved, ingredientOf, expiry, packagesOf);

  function submitStock() {
    // la guardia al posto di `disabled`: il pulsante resta dov'è il fuoco
    if (entries.length === 0 || stock.isPending) return;
    stock.mutate({ sent: entries, left: itemsLeft(items, entries) });
  }

  function renderMatch(item: ShoppingItem, open: MatchPanelState) {
    return (
      <MatchPanel
        key={item.id}
        item={item}
        onMatched={(ingredient) => matchIngredient(open, item, ingredient)}
        onCancel={() => closePanel(open, "match")}
      />
    );
  }

  function renderResolver(item: ShoppingItem, open: ResolverPanelState) {
    // ogni pannello di una confezione lega un prodotto a un ingrediente: una voce senza
    // non ha le tre icone, e un pannello rimasto aperto su di lei non ha niente da
    // mostrare. Lo scanner in particolare confronta il prodotto trovato con questo
    // ingrediente (la guardia del 409): senza, non ha niente con cui confrontarlo
    const ingredientId = ingredientOf(item);
    if (!ingredientId) return null;
    const key = open.packageKey;
    return (
      <ProductResolver
        // un'apertura, un resolver: il codice scritto a mano per un'altra confezione non
        // sopravvive nel campo (S8), e un esito tardivo trova il resolver già smontato
        key={`${key}:${open.serial}`}
        label={item.raw_text}
        ingredient={{ id: ingredientId, name: ingredientNameOf(item), kind: kindOf(item) }}
        start={open.start}
        rememberedCode={rememberedCode[key]}
        onRememberCode={(code) =>
          setRememberedCode((prev) => (code ? { ...prev, [key]: code } : without(prev, key)))
        }
        onResolved={(resolution) => resolve(key, resolution)}
        onStep={(trigger) => setReturnFocus({ key, target: trigger })}
        onCancel={(trigger) => closePanel(open, trigger)}
      />
    );
  }

  /** Il pannello aperto sotto questa confezione, se è suo. «Abbina» sta sotto la voce,
   * cioè sotto la sua prima confezione. */
  function panelFor(item: ShoppingItem, packageKey: string): ReactNode {
    if (!panel || panel.itemId !== item.id) return null;
    if (panel.kind === "match") return packageKey === item.id ? renderMatch(item, panel) : null;
    return panel.packageKey === packageKey ? renderResolver(item, panel) : null;
  }

  /** Dove rimettere il fuoco in questa confezione, quando rinasce. Una richiesta
   * esplicita vince sempre, anche se è per un'altra confezione: gli effetti delle righe
   * girano in ordine di albero, e una voce abbinata che viene prima prenderebbe il fuoco
   * dal `body` lasciando senza la riga che l'aveva chiesto. La richiesta dopo
   * l'abbinamento vale solo per la prima confezione della voce riletta col suo
   * ingrediente: prima, la riga è ancora quella di «Senza reparto» che sta per sparire. */
  function returnFocusFor(packageKey: string, item: ShoppingItem): FocusTarget | null {
    if (returnFocus) return returnFocus.key === packageKey ? returnFocus.target : null;
    if (packageKey === item.id && refocusAfterMatch === item.id && item.ingredient_id) {
      return resolved[item.id] ? "change" : "scanner";
    }
    return null;
  }

  function renderRow(item: ShoppingItem) {
    const keys = packagesOf(item);
    const extras = keys.slice(1);
    // «+ un'altra confezione» quando ogni confezione che c'è ha la sua scelta: su una
    // voce risolta (bozza §10.2), senza impilare confezioni vuote
    const canAddPackage = ingredientOf(item) !== null && keys.every((key) => key in resolved);
    return (
      <StockingRow
        key={item.id}
        item={item}
        resolution={resolved[item.id]}
        ingredientId={ingredientOf(item)}
        expiry={expiry[item.id]}
        onExpiry={(value) => writeExpiry(item.id, value)}
        matchNotSaved={item.id in matchNotSaved}
        retryingMatch={persistMatch.isPending}
        onRetryMatch={() => persistMatch.mutate({ item, ingredient: matchNotSaved[item.id] })}
        focused={panel?.itemId === item.id}
        returnFocusTo={returnFocusFor(item.id, item)}
        onFocusReturned={clearReturnFocus}
        onOpen={(trigger) => openPanelFor(item, item.id, trigger)}
        onLoose={() => resolve(item.id, { kind: "loose" })}
        onChange={() => changeResolution(item.id)}
        after={
          extras.length > 0 || canAddPackage ? (
            <div className="flex flex-col pl-3">
              {extras.map((key, index) => (
                <PackageRow
                  key={key}
                  name={item.raw_text}
                  index={index + 2}
                  resolution={resolved[key]}
                  expiry={expiry[key]}
                  onExpiry={(value) => writeExpiry(key, value)}
                  returnFocusTo={returnFocusFor(key, item)}
                  onFocusReturned={clearReturnFocus}
                  onOpen={(trigger) => openPanelFor(item, key, trigger)}
                  onLoose={() => resolve(key, { kind: "loose" })}
                  onChange={() => changeResolution(key)}
                  onRemove={() => removePackage(item, key)}
                >
                  {panelFor(item, key)}
                </PackageRow>
              ))}
              {canAddPackage && (
                <button
                  type="button"
                  onClick={() => addPackage(item)}
                  className="flex min-h-11 items-center self-start text-xs font-medium text-ink-faint"
                >
                  {/* come «+ scadenza»: piccolo, e il nome della voce solo per chi
                      ascolta, con lo spazio fuori dallo `sr-only` (Chromium lo mangia) */}
                  + un'altra confezione <span className="sr-only">di {item.raw_text}</span>
                </button>
              )}
            </div>
          ) : undefined
        }
      >
        {panelFor(item, item.id)}
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
          // il pannello. Le scelte fatte sulle altre sono indicizzate per confezione, e restano
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
                {/* in fondo, prima di «Metti in dispensa»: si aggiunge quel che manca,
                    poi si mette tutto in dispensa. Solo con qualcosa da sistemare (C, deciso
                    da Mattia il 2026-10-09): a schermo vuoto la strada è la Lista, o la Dispensa */}
                {extraOpen ? (
                  <div className="flex flex-col gap-3 rounded-card border border-line bg-card p-3">
                    <h2 className="font-semibold">Articolo aggiuntivo</h2>
                    <IngredientChooser
                      label="Cosa hai comprato?"
                      failureNote="Puoi comunque aggiungerlo."
                      initialTerm=""
                      busy={addExtra.isPending}
                      onChosen={(ingredient) => {
                        if (!addExtra.isPending) addExtra.mutate(ingredient);
                      }}
                      before={
                        <p className="text-sm text-ink-soft">
                          Entra in lista già spuntato, e lo sistemi qui come le altre voci.
                        </p>
                      }
                      after={
                        <Button
                          variant="ghost"
                          onClick={() => {
                            addExtra.reset();
                            setExtraOpen(false);
                          }}
                          className="self-start"
                        >
                          Annulla
                        </Button>
                      }
                    />
                    {addExtra.isError && (
                      <Alert>Non sono riuscito ad aggiungerlo alla spesa da sistemare. Riprova.</Alert>
                    )}
                  </div>
                ) : (
                  <Button icon={IconPlus} onClick={() => setExtraOpen(true)} className="self-start">
                    Articolo aggiuntivo
                  </Button>
                )}
                {stock.isError && (
                  <div className="flex flex-col items-start gap-2">
                    <p role="alert" className="text-sm text-danger">
                      {stockFailureMessage(stock.error)}
                    </p>
                    {/* un 404 è l'unico caso in cui riprovare così com'è non può
                        riuscire: la lista va riletta. Le scelte sono indicizzate per
                        confezione, quindi sopravvivono alla rilettura — e quelle della
                        voce sparita restano fuori dal corpo da sé */}
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
                {/* `busy` in volo, `unavailableReason` a zero voci (Consegna 6a): tutti e
                    due tengono il fuoco, e il perché — un pulsante spento e muto non si
                    spiega da sé, dal giro — lo scrive Button sotto di sé. Il numero è
                    quello delle confezioni che partono davvero */}
                <Button
                  variant="primary"
                  shape="block"
                  icon={IconPackageImport}
                  busy={stock.isPending}
                  unavailableReason={
                    entries.length === 0
                      ? "Scegli come entra almeno una voce: codice, catalogo o sfuso."
                      : undefined
                  }
                  onClick={submitStock}
                >
                  {entries.length > 0 ? `Metti in dispensa ${entries.length}` : "Metti in dispensa"}
                </Button>
              </div>
            </>
          )
        )}
      </div>
    </Screen>
  );
}

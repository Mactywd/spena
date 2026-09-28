import { useCallback, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { IngredientPicker } from "../../components/IngredientPicker";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { EmptyState } from "../../components/ui/EmptyState";
import { ErrorState } from "../../components/ui/ErrorState";
import { Screen } from "../../components/ui/Screen";
import { Section } from "../../components/ui/Section";
import { ActionBar } from "../../components/ui/ActionBar";
import { IconCalendarEvent, IconPlus, IconSearch, IconX } from "../../components/ui/icons";
import { useNotice } from "../../components/ui/noticeContext";
import { PantryRow } from "./PantryRow";
import { expiryCounts, expirySummary, groupForDisplay, hasExpiry, itemLabel, matchesQuery } from "./pantryView";
import { addPantryItem, fetchPantry, patchPantryItem, restockPantryItem } from "./api";
import { fetchShoppingList } from "../shopping-list/api";
import { ShoppingEntryCard } from "../shopping-list/ShoppingEntryCard";
import type { Ingredient, PantryItem, PantryStatus } from "../../domain/types";

export function PantryScreen() {
  const queryClient = useQueryClient();
  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ["pantry"],
    queryFn: fetchPantry,
  });
  // un caricamento fallito non è una dispensa vuota; ma se un caricamento era già
  // riuscito, React Query ne tiene i dati anche quando il successivo fallisce, e quelli
  // restano a video sotto l'errore. `loaded` distingue i due casi
  const loaded = data !== undefined;
  const items = data ?? [];

  // la stessa chiave dello schermo Lista: la cache è una sola, e aprire la dispensa
  // dopo la lista non ricarica niente. Passiamo i dati e l'errore a ShoppingEntryCard,
  // che decide la nota e conta quel che è nel carrello.
  const { data: shopping, isError: isShoppingError } = useQuery({
    queryKey: ["shopping-list"],
    queryFn: () => fetchShoppingList(),
  });

  // quali voci hanno rifiutato l'ultima modifica. Un insieme, non un solo id:
  // una PATCH di stato su una voce e un annulla fallito su un'altra sono
  // indipendenti, e un singolo id li farebbe scavalcarsi a vicenda. Il messaggio
  // va accanto alla voce giusta e non in cima: la dispensa è lunga e si scorre,
  // un avviso fuori schermo non è un avviso
  const [failedIds, setFailedIds] = useState<Set<string>>(new Set());
  const markFailed = (id: string) =>
    setFailedIds((prev) => (prev.has(id) ? prev : new Set(prev).add(id)));
  const clearFailed = (id: string) =>
    setFailedIds((prev) => {
      if (!prev.has(id)) return prev;
      const next = new Set(prev);
      next.delete(id);
      return next;
    });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["pantry"] });

  const status = useMutation({
    mutationFn: ({ id, status }: { id: string; status: PantryStatus }) =>
      patchPantryItem(id, { status }),
    onMutate: ({ id }) => clearFailed(id),
    onSuccess: invalidate,
    onError: (_error, { id }) => markFailed(id),
  });

  // la scadenza, sulla falsariga di `status` qui sopra: stessa forma, stesso terzetto
  // di handler. `expiresOn` nullo cancella la data — mandarla come `{}` non
  // funzionerebbe: il backend rifiuta un corpo vuoto con 400.
  const expiry = useMutation({
    mutationFn: ({ id, expiresOn }: { id: string; expiresOn: string | null }) =>
      patchPantryItem(id, { expires_on: expiresOn }),
    onMutate: ({ id }) => clearFailed(id),
    onSuccess: invalidate,
    onError: (_error, { id }) => markFailed(id),
  });

  const notice = useNotice();

  // L'annulla vive nell'avviso, che è dell'app e non di questo schermo: si può
  // toccare anche dopo essere passati a un'altra scheda. Per questo non è una
  // useMutation (legata al componente) ma una chiamata col queryClient dell'app.
  // Se fallisce, un nuovo avviso lo dice e offre di riprovare: la voce è archiviata
  // davvero, e perderla qui sarebbe il vicolo cieco.
  function undoRemove(item: PantryItem) {
    patchPantryItem(item.id, { archived: false }).then(
      () => queryClient.invalidateQueries({ queryKey: ["pantry"] }),
      () =>
        notice({
          text: `Non sono riuscito a rimettere ${itemLabel(item)} in dispensa.`,
          action: { label: "Riprova", onClick: () => undoRemove(item) },
        })
    );
  }

  const archive = useMutation({
    mutationFn: (item: PantryItem) => patchPantryItem(item.id, { archived: true }),
    onMutate: (item) => clearFailed(item.id),
    onSuccess: (_data, item) => {
      invalidate();
      notice({
        text: `Tolto dalla dispensa: ${itemLabel(item)}`,
        action: { label: "Annulla", onClick: () => undoRemove(item) },
      });
    },
    onError: (_error, item) => markFailed(item.id),
  });

  // Spec §4 e §8.3: l'ingresso diretto, cioè senza passare dalla lista. Serve a chi
  // torna a casa con una cosa che non aveva scritto, e a censire la dispensa la
  // prima volta; senza, l'unica strada era inventare una voce di lista, spuntarla e
  // sistemarla. Entra `available` e sfusa: lo stato si corregge col controllo qui
  // accanto, la marca si aggancia dove c'è un codice da leggere.
  const [addFailed, setAddFailed] = useState(false);

  const [query, setQuery] = useState("");
  const [expiringOnly, setExpiringOnly] = useState(false);
  // il testo con cui si è aperta l'aggiunta; `null` quando è chiusa
  const [adding, setAdding] = useState<string | null>(null);
  // la voce appena aggiunta, da portare in vista quando arriva nell'elenco
  const [revealId, setRevealId] = useState<string | null>(null);
  const clearReveal = useCallback(() => setRevealId(null), []);

  const add = useMutation({
    mutationFn: (ingredient: Ingredient) => addPantryItem(ingredient.id),
    onMutate: () => setAddFailed(false),
    onSuccess: (created, ingredient) => {
      invalidate();
      setAdding(null);
      // la barra torna vuota e il riepilogo si spegne: la riga nuova deve potersi vedere
      setQuery("");
      setExpiringOnly(false);
      setRevealId(created.id);
      notice({ text: `In dispensa: ${ingredient.display_name}` });
    },
    onError: () => setAddFailed(true),
  });

  // il rientro in lista tocca la lista, non la dispensa: si invalida quella chiave,
  // altrimenti tornando in Lista il numero della scheda d'ingresso resta vecchio
  const restock = useMutation({
    mutationFn: (item: PantryItem) => restockPantryItem(item.id),
    onMutate: (item) => clearFailed(item.id),
    onSuccess: (result, item) => {
      queryClient.invalidateQueries({ queryKey: ["shopping-list"] });
      notice({ text: result.added ? `Rimesso in lista: ${item.ingredient_name}` : "Era già in lista." });
    },
    onError: (_error, item) => markFailed(item.id),
  });

  // gli ingredienti con una voce aperta in lista: per loro «In lista» non serve
  // (dal giro: «la domanda del rientro compare anche per ciò che è già in lista»)
  const listedIngredients = new Set(
    (shopping ?? [])
      .filter((entry) => entry.status === "pending" || entry.status === "checked")
      .map((entry) => entry.ingredient_id)
  );

  // quali voci hanno una richiesta in volo. Un insieme, come prima, e per la
  // stessa ragione: un solo id per tutto lo schermo faceva vincere una
  // mutazione sull'altra.
  //
  // Il limite che resta: `variables` tiene solo l'ultima chiamata di ogni mutazione.
  // Due righe che lanciano la stessa mutazione insieme (due tacche toccate su due
  // voci prima che la prima risposta torni) lasciano sbloccata la prima: la sua
  // richiesta è ancora in volo, ma `status.variables.id` dice già la seconda.
  const busyIds = new Set<string>();
  if (status.isPending) busyIds.add(status.variables.id);
  if (archive.isPending) busyIds.add(archive.variables.id);
  if (restock.isPending) busyIds.add(restock.variables.id);
  if (expiry.isPending) busyIds.add(expiry.variables.id);

  const summary = expirySummary(expiryCounts(items));
  // un riepilogo che sparisce (l'ultima voce in scadenza tolta o finita) si porta via
  // il filtro: una dispensa vuota per un filtro invisibile sarebbe una bugia, e quando
  // il riepilogo torna deve tornare non premuto. Si spegne qui, durante il disegno, e
  // non in un effetto: React ridisegna subito con lo stato nuovo, senza un giro in cui
  // il filtro fantasma resta applicato
  if (summary === null && expiringOnly) setExpiringOnly(false);
  // il filtro guarda la data, non il conteggio: una voce finita non conta nel
  // riepilogo ma resta in vista, col suo «In lista» (hasExpiry)
  const visible = items
    .filter((item) => matchesQuery(item, query))
    .filter((item) => !expiringOnly || hasExpiry(item));

  return (
    <Screen title="Dispensa">
      <div className="flex flex-col gap-3">
        <ShoppingEntryCard items={shopping} failed={isShoppingError} />

        <ActionBar
          inputLabel="Cerca o aggiungi in dispensa"
          placeholder="Cerca o aggiungi"
          addLabel="Aggiungi in dispensa"
          leadingIcon={IconSearch}
          value={query}
          onChange={setQuery}
          onAdd={(text) => {
            setAddFailed(false);
            setAdding(text);
          }}
        />

        {adding !== null && (
          <div className="flex flex-col gap-2 rounded-2xl bg-card p-3">
            <div className="flex items-start gap-2">
              <div className="min-w-0 flex-1">
                <IngredientPicker
                  key={adding}
                  label="Ingrediente da mettere in dispensa"
                  initialTerm={adding}
                  autoFocus
                  failureNote="Riprova, oppure scrivilo in lista e sistemalo da lì."
                  // la dispensa non crea ingredienti: quel che l'anagrafica non ha passa
                  // dalla lista, che prende anche il testo libero — la stessa via
                  // d'uscita di `failureNote`, con la strada a portata di dito
                  emptyNote={
                    <>
                      Non è in anagrafica: scrivilo in{" "}
                      <Link to="/lista" className="inline-flex min-h-11 items-center font-medium text-brand">
                        lista
                      </Link>{" "}
                      e sistemalo da lì.
                    </>
                  }
                  onPick={(ingredient) => add.mutate(ingredient)}
                  disabled={add.isPending}
                />
              </div>
              <Button
                variant="ghost"
                icon={IconX}
                label="Chiudi l'aggiunta"
                onClick={() => {
                  setAddFailed(false);
                  setAdding(null);
                }}
              />
            </div>
            <p className="text-xs text-ink-faint">Entra come disponibile e senza marca.</p>
            {/* accanto al controllo che ha fallito, e la scelta non si perde: si
                rifà toccando di nuovo l'ingrediente */}
            {addFailed && (
              <Alert>Non sono riuscito ad aggiungere la voce in dispensa. Riprova.</Alert>
            )}
          </div>
        )}

        {summary !== null && (
          <button
            type="button"
            aria-pressed={expiringOnly}
            onClick={() => setExpiringOnly((prev) => !prev)}
            className={`flex min-h-11 w-full items-center gap-2 rounded-2xl px-3 py-2 text-sm font-medium ${
              expiringOnly ? "bg-expiry text-on-expiry" : "bg-expiry-tint text-expiry"
            }`}
          >
            <IconCalendarEvent aria-hidden="true" className="size-5 shrink-0" stroke={1.8} />
            <span className="flex-1 text-left">{summary}</span>
            {expiringOnly && (
              <IconX aria-hidden="true" className="size-5 shrink-0" stroke={1.8} />
            )}
          </button>
        )}

        {isLoading && <p className="text-ink-soft">Carico…</p>}

        {isError && (
          <ErrorState
            message={
              loaded
                ? "Non sono riuscito ad aggiornare la dispensa. Quella qui sotto è dell'ultimo caricamento."
                : "Non sono riuscito a caricare la dispensa."
            }
            onRetry={() => void refetch()}
            retrying={isFetching}
          />
        )}

        {loaded && visible.length === 0 && query.trim() === "" && (
          <EmptyState
            title="Dispensa vuota"
            body="Sistema la spesa, oppure scrivi qui sopra quello che hai in casa e tocca +."
          />
        )}

        {/* col riepilogo premuto il vuoto è del filtro, non della dispensa: dirlo
            «niente in dispensa» sarebbe falso, e «Aggiungi» ne farebbe un doppione.
            La via d'uscita è spegnere il filtro */}
        {loaded && visible.length === 0 && query.trim() !== "" && expiringOnly && (
          <EmptyState
            title={`Niente in scadenza per «${query.trim()}»`}
            action={<Button onClick={() => setExpiringOnly(false)}>Mostra tutto</Button>}
          />
        )}

        {/* con l'aggiunta già aperta l'offerta sarebbe un doppione del pannello qui sopra */}
        {loaded && visible.length === 0 && query.trim() !== "" && !expiringOnly && (
          <EmptyState
            title={`Niente in dispensa per «${query.trim()}»`}
            action={
              adding === null && (
                <Button
                  icon={IconPlus}
                  onClick={() => {
                    setAddFailed(false);
                    setAdding(query.trim());
                  }}
                >
                  {`Aggiungi «${query.trim()}»`}
                </Button>
              )
            }
          />
        )}

        {loaded &&
          groupForDisplay(visible).map(([category, rows]) => (
            <Section key={category} category={category} count={rows.length}>
              <ul>
                {rows.map((item) => (
                  <PantryRow
                    key={item.id}
                    item={item}
                    busy={busyIds.has(item.id)}
                    failed={failedIds.has(item.id)}
                    listed={listedIngredients.has(item.ingredient_id)}
                    reveal={item.id === revealId}
                    onStatus={(next) => status.mutate({ id: item.id, status: next })}
                    onRemove={() => archive.mutate(item)}
                    onRestock={() => restock.mutate(item)}
                    onExpiry={(expiresOn) => expiry.mutateAsync({ id: item.id, expiresOn })}
                    onRevealed={clearReveal}
                  />
                ))}
              </ul>
            </Section>
          ))}
      </div>
    </Screen>
  );
}

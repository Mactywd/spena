import { useCallback, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "../../components/ui/Button";
import { EmptyState } from "../../components/ui/EmptyState";
import { ErrorState } from "../../components/ui/ErrorState";
import { Screen } from "../../components/ui/Screen";
import { Section } from "../../components/ui/Section";
import { ActionBar } from "../../components/ui/ActionBar";
import { IconBarcode, IconCalendarEvent, IconPlus, IconSearch, IconX } from "../../components/ui/icons";
import { useNotice } from "../../components/ui/noticeContext";
import { DirectEntry, type EntryDoor } from "./DirectEntry";
import { PantryRow } from "./PantryRow";
import {
  expiryCounts,
  expirySummary,
  groupForDisplay,
  hasBothWorlds,
  inWorld,
  itemLabel,
  settleWorld,
  visibleItems,
  WORLD_LABELS,
  type PantryWorld,
} from "./pantryView";
import { loadWorld, saveWorld } from "./pantryWorld";
import { WorldSelector } from "./WorldSelector";
import { fetchPantry, patchPantryItem, restockPantryItem } from "./api";
import { fetchShoppingList } from "../shopping-list/api";
import { ShoppingEntryCard } from "../shopping-list/ShoppingEntryCard";
import type { PantryItem, PantryStatus } from "../../domain/types";

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
      notice({
        text: `Tolto dalla dispensa: ${itemLabel(item)}`,
        action: { label: "Annulla", onClick: () => undoRemove(item) },
      });
      // React Query aspetta la promise che `onSuccess` restituisce prima di lasciare
      // `isPending`: senza questo `return` la riga si sbloccava prima che il riordino
      // fosse arrivato, con la voce ancora a video ma i controlli di nuovo toccabili
      // (stesso difetto di ShoppingListScreen, dal giro)
      return invalidate();
    },
    onError: (_error, item) => markFailed(item.id),
  });

  const [query, setQuery] = useState("");
  const [expiringOnly, setExpiringOnly] = useState(false);
  // S14: il mondo scelto, ricordato per la sessione (`pantryWorld.ts`). Si scrive a ogni
  // cambio, anche quando è il disegno a riportarlo a «Tutto» (`settleWorld`, più giù)
  const [world, setWorld] = useState<PantryWorld>(() => loadWorld());
  useEffect(() => saveWorld(world), [world]);
  // L'ingresso diretto (S3): una confezione che non passa dalla lista — chi torna a
  // casa con una cosa che non aveva scritto, e il censimento della dispensa. Due porte:
  // il + col testo della barra, e «Scansiona». `null` quando è chiuso; `serial` lo fa
  // rinascere quando si riapre con un testo nuovo
  const [entry, setEntry] = useState<{ door: EntryDoor; serial: number } | null>(null);
  // la voce appena aggiunta, da portare in vista quando arriva nell'elenco
  const [revealId, setRevealId] = useState<string | null>(null);
  const clearReveal = useCallback(() => setRevealId(null), []);

  // Un tocco sul selettore, o su «Cerca in tutto», è una scelta esplicita di chi guarda: spegne
  // la riga da portare in vista. Se restasse in sospeso (la riga non monta, per esempio perché
  // la ricerca la filtra via), `settleWorld` riporterebbe a «Tutto» ogni tocco successivo
  function chooseWorld(next: PantryWorld) {
    setRevealId(null);
    setWorld(next);
  }

  function openEntry(door: EntryDoor) {
    setEntry((prev) => ({ door, serial: (prev?.serial ?? 0) + 1 }));
  }

  // L'annulla di un ingresso: archivia la voce appena creata, come la ✕ di una riga.
  // Vive nell'avviso, che è dell'app: se fallisce, un avviso nuovo lo dice e offre di
  // riprovare — la voce è in dispensa davvero, e perderla qui sarebbe il vicolo cieco
  function undoEntry(created: PantryItem, label: string) {
    patchPantryItem(created.id, { archived: true }).then(
      () => queryClient.invalidateQueries({ queryKey: ["pantry"] }),
      () =>
        notice({
          text: `Non sono riuscito a togliere ${label} dalla dispensa.`,
          action: { label: "Riprova", onClick: () => undoEntry(created, label) },
        })
    );
  }

  /** Una confezione è entrata, da una delle due porte. La riga nuova deve potersi
   * vedere: la barra torna vuota, il riepilogo si spegne, e `revealId` la porta in
   * vista quando arriva nell'elenco. Il mondo (S14) non si rimette qui: se la voce è
   * dell'altro mondo ci pensa `settleWorld` nel disegno, guardando `revealId`. Un
   * filtro nuovo (S15) deciderà da sé come farsi da parte. */
  function afterEntry(created: PantryItem, label: string) {
    invalidate();
    setQuery("");
    setExpiringOnly(false);
    setRevealId(created.id);
    notice({
      text: `In dispensa: ${label}`,
      action: { label: "Annulla", onClick: () => undoEntry(created, label) },
    });
  }

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

  // S14 §3 e §4: un selettore che sparisce (un mondo solo) si porta via il suo filtro, e
  // una voce appena aggiunta dell'altro mondo porta a «Tutto», perché si veda. Nel disegno
  // e non in un effetto, come il riepilogo qui sotto: nessun giro col filtro fantasma. Solo
  // a dispensa caricata: la lista vuota del caricamento non è una dispensa con un mondo solo
  const settledWorld = settleWorld(world, items, revealId);
  if (loaded && settledWorld !== world) setWorld(settledWorld);
  const showWorlds = hasBothWorlds(items);
  // il riepilogo conta il mondo scelto (Mattia, 2026-10-07): su «Cibo» dice quanti cibi
  // scadono, o col riepilogo premuto direbbe «2 in scadenza» sopra zero righe
  const summary = expirySummary(expiryCounts(items.filter((item) => inWorld(item, world))));
  // un riepilogo che sparisce (l'ultima voce in scadenza tolta o finita) si porta via
  // il filtro: una dispensa vuota per un filtro invisibile sarebbe una bugia, e quando
  // il riepilogo torna deve tornare non premuto. Si spegne qui, durante il disegno, e
  // non in un effetto: React ridisegna subito con lo stato nuovo, senza un giro in cui
  // il filtro fantasma resta applicato
  if (summary === null && expiringOnly) setExpiringOnly(false);
  // il filtro guarda la data, non il conteggio: una voce finita non conta nel
  // riepilogo ma resta in vista, col suo «In lista» (hasExpiry)
  const visible = visibleItems(items, { world, query, expiringOnly });

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
          onAdd={(text) => openEntry({ kind: "plus", text })}
          // la seconda porta (S3): la confezione in mano, il codice da leggere
          secondaryAction={{
            icon: IconBarcode,
            label: "Scansiona",
            onClick: () => openEntry({ kind: "scan" }),
          }}
        />

        {entry !== null && (
          <DirectEntry
            key={entry.serial}
            door={entry.door}
            onEntered={afterEntry}
            onClose={() => setEntry(null)}
          />
        )}

        {/* S14: sotto la barra (e sotto il pannello dell'aggiunta, quando è aperto), sopra il
            riepilogo che conta il mondo scelto. Solo coi due mondi in dispensa */}
        {showWorlds && <WorldSelector value={world} onChange={chooseWorld} />}

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

        {/* S14 §4: col mondo scelto il vuoto è del mondo, non della dispensa. Il sale può stare
            sotto «Cibo»: «Niente in dispensa» sarebbe falso, e «Aggiungi» ne farebbe un
            doppione. La via d'uscita allarga a «Tutto» e tiene il testo; l'offerta di
            aggiungere torna lì, se anche «Tutto» non trova niente */}
        {loaded && visible.length === 0 && query.trim() !== "" && !expiringOnly && world !== "all" && (
          <EmptyState
            title={`Niente in ${WORLD_LABELS[world]} per «${query.trim()}»`}
            action={<Button onClick={() => chooseWorld("all")}>Cerca in tutto</Button>}
          />
        )}

        {/* con l'aggiunta già aperta l'offerta sarebbe un doppione del pannello qui sopra */}
        {loaded && visible.length === 0 && query.trim() !== "" && !expiringOnly && world === "all" && (
          <EmptyState
            title={`Niente in dispensa per «${query.trim()}»`}
            action={
              entry === null && (
                <Button
                  icon={IconPlus}
                  onClick={() => openEntry({ kind: "plus", text: query.trim() })}
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

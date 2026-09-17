import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { IngredientPicker } from "../../components/IngredientPicker";
import { Alert } from "../../components/ui/Alert";
import { Card } from "../../components/ui/Card";
import { Screen } from "../../components/ui/Screen";
import { SectionEntryCard } from "../../components/ui/SectionEntryCard";
import { SectionHeading } from "../../components/ui/SectionHeading";
import { PantryRow } from "./PantryRow";
import { addPantryItem, fetchPantry, patchPantryItem, restockPantryItem } from "./api";
import { fetchShoppingList } from "../shopping-list/api";
import type { Ingredient, PantryItem } from "../../domain/types";

// quanto dura l'annulla. Sei secondi: il tempo di accorgersi di aver sbagliato
// riga senza che la dispensa resti mezza finta per mezzo minuto
const UNDO_MS = 6000;

/** L'elenco da mostrare: quello del server più le istantanee delle voci appena
 * tolte che il server non manda più. Le lapidi vivono qui e non nella risposta,
 * perché la risposta le esclude e perché ogni invalidazione le cancellerebbe —
 * e con loro l'unico annulla che l'interfaccia offre. Una voce tolta ma ancora
 * presente nella risposta (l'archiviazione non invalida) resta al suo posto: la
 * chiave `id` evita il doppione. */
function withRemoved(items: PantryItem[], removed: Map<string, PantryItem>): PantryItem[] {
  if (removed.size === 0) return items;
  const present = new Set(items.map((item) => item.id));
  return [...items, ...[...removed.values()].filter((item) => !present.has(item.id))];
}

function groupByCategory(items: PantryItem[]): [string, PantryItem[]][] {
  const groups = new Map<string, PantryItem[]>();
  for (const item of items) {
    groups.set(item.ingredient_category, [...(groups.get(item.ingredient_category) ?? []), item]);
  }
  return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b));
}

export function PantryScreen() {
  const queryClient = useQueryClient();
  const { data: items = [], isLoading, isError } = useQuery({
    queryKey: ["pantry"],
    queryFn: fetchPantry,
  });

  // la stessa chiave dello schermo Lista: la cache è una sola, e aprire la dispensa
  // dopo la lista non ricarica niente. Se non risponde non si mostra un conteggio
  // sbagliato — la scheda resta, con una nota che non promette nulla: l'ingresso
  // alla sottosezione non deve dipendere da una seconda chiamata
  const { data: shopping, isError: isShoppingError } = useQuery({
    queryKey: ["shopping-list"],
    queryFn: () => fetchShoppingList(),
  });
  const checkedCount = (shopping ?? []).filter((item) => item.status === "checked").length;

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

  const change = useMutation({
    mutationFn: ({ id, fill }: { id: string; fill: number }) =>
      patchPantryItem(id, { fill_percent: fill }),
    onMutate: ({ id }) => clearFailed(id),
    onSuccess: invalidate,
    // senza questo una PATCH fallita non dice niente: il cursore torna da sé al
    // valore del server e l'utente resta convinto di averlo spostato
    onError: (_error, { id }) => markFailed(id),
  });

  // le voci appena tolte, finché il loro annulla è possibile. Una mappa, non un
  // solo id: togliere una seconda voce prima che scada la lapide della prima non
  // deve spegnere quella della prima. E si tiene la VOCE, non solo il suo id,
  // perché il server non manda più le voci archiviate (`list_pantry` filtra
  // `archived_at IS NULL`): l'archiviazione di suo non invalida, ma ogni altra
  // mutazione dello schermo sì, e una lapide che dipendesse dalla riga del
  // server svanirebbe muta al primo cursore mosso altrove — con essa l'unico
  // modo di disarchiviare che l'interfaccia abbia. L'istantanea qui dentro è
  // quella che tiene in piedi la lapide, e `withRemoved` la unisce all'elenco.
  const [removed, setRemoved] = useState<Map<string, PantryItem>>(new Map());
  const addRemoved = (item: PantryItem) =>
    setRemoved((prev) => new Map(prev).set(item.id, item));
  const clearRemoved = (id: string) =>
    setRemoved((prev) => {
      if (!prev.has(id)) return prev;
      const next = new Map(prev);
      next.delete(id);
      return next;
    });

  // un timer per lapide, non uno per lo schermo: altrimenti il cleanup dello
  // useEffect sulla lapide precedente la spegnerebbe quando ne parte una nuova
  const undoTimers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());
  const stopUndoTimer = (id: string) => {
    const timer = undoTimers.current.get(id);
    if (timer !== undefined) {
      clearTimeout(timer);
      undoTimers.current.delete(id);
    }
  };
  const startUndoTimer = (id: string) => {
    stopUndoTimer(id);
    undoTimers.current.set(
      id,
      setTimeout(() => {
        undoTimers.current.delete(id);
        clearRemoved(id);
        invalidate();
      }, UNDO_MS)
    );
  };
  // niente lapide sopravvive allo schermo: senza questo, uno unmount a metà dei
  // sei secondi (i test lo fanno a ogni riga) lascerebbe un timer acceso che
  // invalida una query di un componente non più a video
  useEffect(() => {
    return () => {
      undoTimers.current.forEach(clearTimeout);
      undoTimers.current.clear();
    };
  }, []);

  // Archiviare è l'unico modo di togliere qualcosa dalla dispensa: il backend
  // esclude le voci finite dalla disponibilità ma non dall'elenco, quindi senza
  // questo controllo lo schermo può soltanto crescere. Prende la voce intera e
  // non il suo id: quello che entra in `removed` è l'istantanea della riga che
  // l'utente aveva davanti, l'unica copia che resterà quando il server smetterà
  // di mandarla.
  const archive = useMutation({
    mutationFn: (item: PantryItem) => patchPantryItem(item.id, { archived: true }),
    onMutate: (item) => clearFailed(item.id),
    onSuccess: (_data, item) => {
      addRemoved(item);
      startUndoTimer(item.id);
    },
    onError: (_error, item) => markFailed(item.id),
  });

  // l'annulla di una lapide. Se fallisce, la lapide RESTA — l'istantanea non si
  // toglie da `removed` — perché la voce è archiviata davvero sul server e
  // perderla qui lascerebbe l'utente senza messaggio e senza modo di riprovare:
  // esattamente il vicolo cieco che «mai un vicolo cieco» vieta. Il timer si
  // spegne appena si tenta l'annulla, per non far scadere una lapide che sta
  // mostrando un errore.
  const undo = useMutation({
    mutationFn: (id: string) => patchPantryItem(id, { archived: false }),
    onMutate: (id) => {
      stopUndoTimer(id);
      clearFailed(id);
    },
    onSuccess: (_data, id) => {
      clearRemoved(id);
      invalidate();
    },
    onError: (_error, id) => markFailed(id),
  });

  // Spec §4 e §8.3: l'ingresso diretto, cioè senza passare dalla lista. Serve a chi
  // torna a casa con una cosa che non aveva scritto, e a censire la dispensa la
  // prima volta; senza, l'unica strada era inventare una voce di lista, spuntarla e
  // sistemarla. Entra `available` e sfusa: lo stato si corregge col controllo qui
  // accanto, la marca si aggancia dove c'è un codice da leggere.
  const [addFailed, setAddFailed] = useState(false);
  const add = useMutation({
    mutationFn: (ingredient: Ingredient) => addPantryItem(ingredient.id),
    onMutate: () => setAddFailed(false),
    onSuccess: invalidate,
    onError: () => setAddFailed(true),
  });

  // il rientro in lista tocca la lista, non la dispensa: si invalida quella chiave,
  // altrimenti tornando in Lista il numero della scheda d'ingresso resta vecchio
  const restock = useMutation({
    mutationFn: (id: string) => restockPantryItem(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["shopping-list"] }),
  });

  // quali voci hanno una richiesta in volo. Un insieme, come gli altri due, e
  // per la stessa ragione: un solo id per tutto lo schermo faceva vincere una
  // mutazione sull'altra, e con la PATCH del cursore della riga A in volo i
  // «Sì»/«No» della riga B restavano premibili anche mentre il POST di B era in
  // corso — proprio quello che questa guardia dichiara di impedire.
  // `busy` disabilita anche «Annulla» e «Sì»/«No» del rientro in lista: un
  // doppio clic non deve mandare due PATCH di annulla (innocuo perché la PATCH
  // è idempotente, ma inutile) né due POST di restock (quello non è idempotente,
  // e `shopping_list_items` non ha un vincolo unico che lo rimedi a valle).
  // Quel che l'insieme NON copre: `variables` tiene solo l'ultima invocazione di
  // ciascuna mutazione, quindi due righe che lanciano la STESSA mutazione insieme
  // lasciano sbloccata la prima. Servirebbe un conteggio per id (useMutationState);
  // oggi non lo facciamo perché richiede due gesti in righe diverse entro la
  // durata di una richiesta, ma il caso esiste e questa riga esiste per non
  // lasciar credere il contrario.
  const busyIds = new Set<string>();
  if (change.isPending) busyIds.add(change.variables.id);
  if (archive.isPending) busyIds.add(archive.variables.id);
  if (undo.isPending) busyIds.add(undo.variables);
  if (restock.isPending) busyIds.add(restock.variables);

  // l'elenco a video: risposta del server più le lapidi che il server non manda
  // più (vedi `withRemoved`). Se il caricamento fallisce la risposta del server
  // sparisce — sarebbe quella di prima, e nessuno saprebbe che è vecchia — ma le
  // lapidi no: non vengono dal server, e senza di loro una voce appena tolta
  // resta archiviata davvero senza più nessun tasto per riportarla indietro
  const rows = withRemoved(isError ? [] : items, removed);

  return (
    <Screen title="Dispensa">
      <SectionEntryCard
        to="/sistema"
        title="Sistema la spesa"
        note={
          isShoppingError || shopping === undefined
            ? "Metti via quello che hai comprato"
            : checkedCount === 0
              ? "Niente di spuntato, per ora"
              : checkedCount === 1
                ? "1 voce spuntata da mettere via"
                : `${checkedCount} voci spuntate da mettere via`
        }
        pending={checkedCount > 0}
      />

      <Card>
        <IngredientPicker
          label="Aggiungi in dispensa"
          failureNote="Riprova, oppure scrivilo in lista e sistemalo da lì."
          onPick={(ingredient) => add.mutate(ingredient)}
          disabled={add.isPending}
        />
        <p className="pt-2 text-xs text-ink-faint">
          Entra come disponibile e senza marca. Lo stato si cambia qui sotto.
        </p>
        {/* accanto al controllo che ha fallito, e la scelta non si perde: si
            rifà toccando di nuovo l'ingrediente */}
        {addFailed && (
          <Alert className="pt-2">
            Non sono riuscito ad aggiungere la voce in dispensa. Riprova.
          </Alert>
        )}
      </Card>

      {isLoading && <p className="pt-4 text-ink-soft">Carico…</p>}

      {/* un caricamento fallito non è una dispensa vuota: dirlo sarebbe una bugia
          su quello che c'è da mangiare */}
      {isError && (
        <Alert className="pt-4">
          Non sono riuscito a caricare la dispensa. Riprova più tardi.
        </Alert>
      )}

      {!isLoading && !isError && rows.length === 0 && (
        <p className="pt-4 text-ink-soft">
          Dispensa vuota. Sistema la spesa, oppure aggiungi qui sopra quello che hai in casa.
        </p>
      )}

      {!isLoading && rows.length > 0 &&
        groupByCategory(rows).map(([category, group]) => (
          <section key={category}>
            <SectionHeading>{category}</SectionHeading>
            <Card pad={false}>
              <ul className="divide-y divide-line">
                {group.map((item) => (
                  <PantryRow
                    key={item.id}
                    item={item}
                    busy={busyIds.has(item.id)}
                    removed={removed.has(item.id)}
                    failed={failedIds.has(item.id)}
                    onFill={(percent) => change.mutateAsync({ id: item.id, fill: percent })}
                    onRemove={() => archive.mutate(item)}
                    onUndo={() => undo.mutate(item.id)}
                    onRestock={() => restock.mutateAsync(item.id)}
                  />
                ))}
              </ul>
            </Card>
          </section>
        ))}
    </Screen>
  );
}

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AddItemField } from "./AddItemField";
import { ListRow } from "./ListRow";
import { ShoppingEntryCard } from "./ShoppingEntryCard";
import { groupForDisplay } from "./listView";
import { addShoppingItem, fetchShoppingList, patchShoppingItem } from "./api";
import { ApiError } from "../../api/client";
import { EmptyState } from "../../components/ui/EmptyState";
import { ErrorState } from "../../components/ui/ErrorState";
import { Screen } from "../../components/ui/Screen";
import { Section } from "../../components/ui/Section";
import { useNotice } from "../../components/ui/noticeContext";
import type { ShoppingItem } from "../../domain/types";

// la stessa chiave della Dispensa, che ne legge la scheda d'ingresso: la cache è una
const LIST_KEY = ["shopping-list"];

export function ShoppingListScreen() {
  const queryClient = useQueryClient();
  const notice = useNotice();
  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: LIST_KEY,
    queryFn: () => fetchShoppingList(),
  });
  // un caricamento fallito non è una lista vuota; ma se uno era già riuscito, React
  // Query ne tiene i dati anche quando il successivo fallisce, e quelli restano a video
  // sotto l'errore. `loaded` distingue i due casi, come in PantryScreen
  const loaded = data !== undefined;
  const items = data ?? [];

  // quali voci hanno rifiutato l'ultima modifica. Un insieme, non un solo id: una
  // spunta fallita su una voce e un «Annulla» fallito su un'altra sono indipendenti.
  // Il messaggio va accanto alla voce e non in cima: la lista si scorre camminando per
  // i reparti, e un avviso fuori schermo non è un avviso
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

  const invalidate = () => queryClient.invalidateQueries({ queryKey: LIST_KEY });

  const add = useMutation({
    mutationFn: ({ text, id }: { text: string; id?: string }) => addShoppingItem(text, id),
    onSuccess: invalidate,
  });

  const toggle = useMutation({
    mutationFn: (item: ShoppingItem) =>
      patchShoppingItem(item.id, { status: item.status === "checked" ? "pending" : "checked" }),
    onMutate: (item) => clearFailed(item.id),
    onSuccess: invalidate,
    // senza questo una PATCH fallita non dice niente: la casella torna da sé al valore
    // del server e chi guarda resta convinto di aver spuntato
    onError: (_error, item) => markFailed(item.id),
  });

  // L'annulla vive nell'avviso, che è dell'app e non di questo schermo: si può toccare
  // anche dopo essere passati a un'altra scheda. Per questo non è una useMutation
  // (legata al componente) ma una chiamata col queryClient dell'app, come in
  // PantryScreen. La voce torna allo stato che aveva — da comprare o nel carrello —
  // con la PATCH di sempre (spec §4.2).
  function undoRemove(item: ShoppingItem) {
    // nei 6 secondi dell'avviso la stessa cosa può essere stata riscritta dalla barra:
    // rimettere anche questa farebbe il doppione che S18 esiste per evitare. La cache è
    // la via veloce, non la difesa: fra la POST della barra e il refetch non lo sa
    // ancora, e allora risponde il server, con un 409 (sotto)
    const current = queryClient.getQueryData<ShoppingItem[]>(LIST_KEY) ?? [];
    const relisted =
      item.ingredient_id !== null &&
      current.some((other) => other.id !== item.id && other.ingredient_id === item.ingredient_id);
    if (relisted) {
      notice({ text: "Era già in lista." });
      return;
    }
    patchShoppingItem(item.id, { status: item.status }).then(
      () => queryClient.invalidateQueries({ queryKey: LIST_KEY }),
      (error: unknown) => {
        // la stessa notizia della barra, non un guasto: niente «Riprova», che
        // rifallirebbe. Si rilegge la lista, così la voce che c'è si vede
        if (error instanceof ApiError && error.status === 409) {
          notice({ text: "Era già in lista." });
          void queryClient.invalidateQueries({ queryKey: LIST_KEY });
          return;
        }
        // la voce è archiviata davvero: perderla qui sarebbe il vicolo cieco
        notice({
          text: `Non sono riuscito a rimettere ${item.raw_text} in lista.`,
          action: { label: "Riprova", onClick: () => undoRemove(item) },
        });
      }
    );
  }

  // Archiviare è l'unico modo di togliere una voce: «pomdoro» scritto per sbaglio non
  // si cancella spuntandolo, perché spuntarlo lo fa entrare in dispensa — cioè sporca
  // la dispensa per pulire la lista. `fetchShoppingList` chiede solo `pending` e
  // `checked`, quindi la riga sparisce senza altro lavoro.
  const archive = useMutation({
    mutationFn: (item: ShoppingItem) => patchShoppingItem(item.id, { status: "archived" }),
    onMutate: (item) => clearFailed(item.id),
    onSuccess: (_data, item) => {
      notice({
        text: `Tolto dalla lista: ${item.raw_text}`,
        action: { label: "Annulla", onClick: () => undoRemove(item) },
      });
      // React Query aspetta la promise che `onSuccess` restituisce prima di lasciare
      // `isPending`: senza questo `return` la riga si sbloccava prima che il riordino
      // fosse arrivato, con la voce ancora a video ma la casella di nuovo toccabile (dal
      // giro)
      return invalidate();
    },
    onError: (_error, item) => markFailed(item.id),
  });

  // quali voci hanno una richiesta in volo: due PATCH sulla stessa riga arrivano in
  // ordine ignoto e l'ultima a rispondere vince. Il limite è quello di PantryScreen:
  // `variables` tiene solo l'ultima chiamata di ogni mutazione
  const busyIds = new Set<string>();
  if (toggle.isPending) busyIds.add(toggle.variables.id);
  if (archive.isPending) busyIds.add(archive.variables.id);

  return (
    <Screen title="Lista">
      <div className="flex flex-col gap-3">
        <AddItemField onAdd={(text, id) => add.mutateAsync({ text, id })} />

        {/* sempre presente, anche a carrello vuoto: «Sistema la spesa» è una
            sottosezione, non un avviso (D3 di docs/prossimi-passi.md) */}
        <ShoppingEntryCard items={data} failed={isError} />

        {isLoading && <p className="text-ink-soft">Carico…</p>}

        {/* scrivere resta possibile in ogni caso: la barra è sopra, e non dipende dal
            caricamento */}
        {isError && (
          <ErrorState
            message={
              loaded
                ? "Non sono riuscito ad aggiornare la lista. Quella qui sotto è dell'ultimo caricamento."
                : "Non sono riuscito a caricare la lista. Puoi comunque aggiungere voci."
            }
            onRetry={() => void refetch()}
            retrying={isFetching}
          />
        )}

        {loaded && items.length === 0 && (
          <EmptyState title="Lista vuota" body="Scrivi qui sopra cosa ti serve e tocca +." />
        )}

        {loaded &&
          groupForDisplay(items).map(([category, rows]) => (
            <Section key={category ?? "senza-reparto"} category={category} count={rows.length}>
              <ul>
                {rows.map((item) => (
                  <ListRow
                    key={item.id}
                    item={item}
                    busy={busyIds.has(item.id)}
                    failed={failedIds.has(item.id)}
                    onToggle={() => toggle.mutate(item)}
                    onRemove={() => archive.mutate(item)}
                  />
                ))}
              </ul>
            </Section>
          ))}
      </div>
    </Screen>
  );
}

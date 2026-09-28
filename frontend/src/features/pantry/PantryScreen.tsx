import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { IngredientPicker } from "../../components/IngredientPicker";
import { Alert } from "../../components/ui/Alert";
import { Card } from "../../components/ui/Card";
import { Screen } from "../../components/ui/Screen";
import { SectionEntryCard } from "../../components/ui/SectionEntryCard";
import { SectionHeading } from "../../components/ui/SectionHeading";
import { useNotice } from "../../components/ui/noticeContext";
import { PantryRow } from "./PantryRow";
import { itemLabel } from "./pantryView";
import { addPantryItem, fetchPantry, patchPantryItem, restockPantryItem } from "./api";
import { fetchShoppingList } from "../shopping-list/api";
import type { Ingredient, PantryItem, PantryStatus } from "../../domain/types";

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

  const status = useMutation({
    mutationFn: ({ id, status }: { id: string; status: PantryStatus }) =>
      patchPantryItem(id, { status }),
    onMutate: ({ id }) => clearFailed(id),
    onSuccess: invalidate,
    onError: (_error, { id }) => markFailed(id),
  });

  // la scadenza, sulla falsariga di `change`: stessa forma, stesso terzetto di
  // handler. `expiresOn` nullo cancella la data — mandarla come `{}` non
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
  const add = useMutation({
    mutationFn: (ingredient: Ingredient) => addPantryItem(ingredient.id),
    onMutate: () => setAddFailed(false),
    onSuccess: invalidate,
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
  const busyIds = new Set<string>();
  if (status.isPending) busyIds.add(status.variables.id);
  if (archive.isPending) busyIds.add(archive.variables.id);
  if (restock.isPending) busyIds.add(restock.variables.id);
  if (expiry.isPending) busyIds.add(expiry.variables.id);

  const rows = isError ? [] : items;

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
              <ul>
                {group.map((item) => (
                  <PantryRow
                    key={item.id}
                    item={item}
                    busy={busyIds.has(item.id)}
                    failed={failedIds.has(item.id)}
                    listed={listedIngredients.has(item.ingredient_id)}
                    reveal={false}
                    onStatus={(next) => status.mutate({ id: item.id, status: next })}
                    onRemove={() => archive.mutate(item)}
                    onRestock={() => restock.mutate(item)}
                    onExpiry={(expiresOn) => expiry.mutateAsync({ id: item.id, expiresOn })}
                    onRevealed={() => {}}
                  />
                ))}
              </ul>
            </Card>
          </section>
        ))}
    </Screen>
  );
}

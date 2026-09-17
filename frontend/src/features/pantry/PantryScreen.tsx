import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { StatusToggle } from "./StatusToggle";
import { IngredientPicker } from "../../components/IngredientPicker";
import { Alert } from "../../components/ui/Alert";
import { Card } from "../../components/ui/Card";
import { Screen } from "../../components/ui/Screen";
import { SectionEntryCard } from "../../components/ui/SectionEntryCard";
import { SectionHeading } from "../../components/ui/SectionHeading";
import { addPantryItem, fetchPantry, patchPantryItem } from "./api";
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

  // quale voce ha rifiutato l'ultima modifica. Il messaggio va accanto a quella
  // voce e non in cima: la dispensa è lunga e si scorre, un avviso fuori schermo
  // non è un avviso
  const [failedId, setFailedId] = useState<string | null>(null);
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["pantry"] });

  const change = useMutation({
    mutationFn: ({ id, status }: { id: string; status: PantryStatus }) =>
      patchPantryItem(id, { status }),
    onMutate: () => setFailedId(null),
    onSuccess: invalidate,
    // senza questo una PATCH fallita non dice niente: il controllo torna da sé al
    // valore del server e l'utente resta convinto di aver cambiato stato
    onError: (_error, { id }) => setFailedId(id),
  });

  // Archiviare è l'unico modo di togliere qualcosa dalla dispensa: il backend
  // esclude le voci finite dalla disponibilità ma non dall'elenco, quindi senza
  // questo controllo lo schermo può soltanto crescere.
  const archive = useMutation({
    mutationFn: (id: string) => patchPantryItem(id, { archived: true }),
    onMutate: () => setFailedId(null),
    onSuccess: invalidate,
    onError: (_error, id) => setFailedId(id),
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

  const busyId = change.isPending
    ? change.variables.id
    : archive.isPending
      ? archive.variables
      : null;

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

      {!isLoading && !isError && items.length === 0 && (
        <p className="pt-4 text-ink-soft">
          Dispensa vuota. Sistema la spesa, oppure aggiungi qui sopra quello che hai in casa.
        </p>
      )}

      {!isLoading && !isError && items.length > 0 &&
        groupByCategory(items).map(([category, group]) => (
          <section key={category}>
            <SectionHeading>{category}</SectionHeading>
            <Card pad={false}>
              <ul className="divide-y divide-line">
                {group.map((item) => (
                  <li key={item.id} className="flex flex-col gap-2.5 p-3">
                    <div>
                      {/* la marca che hai comprato è più utile del nome generico */}
                      <span className="font-medium">{item.product_name ?? item.ingredient_name}</span>
                      {/* lo spazio è scritto a mano perché `ml-2` è un margine, non del
                          testo: senza, il nome accessibile della riga si legge
                          «Total 0%Fage» e chi usa uno screen reader sente una parola sola */}
                      {item.product_brand && (
                        <>
                          {" "}
                          <span className="text-sm text-ink-faint">{item.product_brand}</span>
                        </>
                      )}
                    </div>
                    <StatusToggle
                      value={item.status}
                      disabled={busyId === item.id}
                      onChange={(status) => change.mutate({ id: item.id, status })}
                    />
                    {/* il testo è quello di prima: è anche il nome con cui si comanda
                        a voce questo bersaglio, e accorciarlo sullo schermo lo
                        scollerebbe da quel nome */}
                    <button
                      type="button"
                      disabled={busyId === item.id}
                      onClick={() => archive.mutate(item.id)}
                      className="self-start py-2 text-xs text-ink-faint underline disabled:opacity-40"
                    >
                      Togli dalla dispensa
                    </button>
                    {failedId === item.id && (
                      <Alert>Non sono riuscito a salvare la modifica. Riprova.</Alert>
                    )}
                  </li>
                ))}
              </ul>
            </Card>
          </section>
        ))}
    </Screen>
  );
}

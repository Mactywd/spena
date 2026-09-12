import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { StatusToggle } from "./StatusToggle";
import { IngredientPicker } from "../../components/IngredientPicker";
import { addPantryItem, fetchPantry, patchPantryItem } from "./api";
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
    <div className="p-4">
      <h1 className="pb-3 text-xl font-semibold">Dispensa</h1>

      <section className="border-b border-neutral-100 pb-4">
        <IngredientPicker
          label="Aggiungi in dispensa"
          failureNote="Riprova, oppure scrivilo in lista e sistemalo da lì."
          onPick={(ingredient) => add.mutate(ingredient)}
          disabled={add.isPending}
        />
        <p className="pt-2 text-xs text-neutral-500">
          Entra come disponibile e senza marca. Lo stato si cambia qui sotto.
        </p>
        {/* accanto al controllo che ha fallito, e la scelta non si perde: si
            rifà toccando di nuovo l'ingrediente */}
        {addFailed && (
          <p role="alert" className="pt-2 text-sm text-red-600">
            Non sono riuscito ad aggiungere la voce in dispensa. Riprova.
          </p>
        )}
      </section>

      {isLoading && <p className="pt-4 text-neutral-500">Carico…</p>}

      {/* un caricamento fallito non è una dispensa vuota: dirlo sarebbe una bugia
          su quello che c'è da mangiare */}
      {isError && (
        <p role="alert" className="pt-4 text-sm text-red-600">
          Non sono riuscito a caricare la dispensa. Riprova più tardi.
        </p>
      )}

      {!isLoading && !isError && items.length === 0 && (
        <p className="pt-4 text-neutral-500">
          Dispensa vuota. Sistema la spesa, oppure aggiungi qui sopra quello che hai in casa.
        </p>
      )}

      {!isLoading && !isError && items.length > 0 &&
        groupByCategory(items).map(([category, group]) => (
          <section key={category} className="pb-4">
            <h2 className="py-2 text-xs uppercase tracking-wide text-neutral-400">{category}</h2>
            <ul className="divide-y divide-neutral-100">
              {group.map((item) => (
                <li key={item.id} className="flex flex-col gap-2 py-3">
                  <div>
                    {/* la marca che hai comprato è più utile del nome generico */}
                    <span className="font-medium">{item.product_name ?? item.ingredient_name}</span>
                    {item.product_brand && (
                      <span className="ml-2 text-sm text-neutral-500">{item.product_brand}</span>
                    )}
                  </div>
                  <StatusToggle
                    value={item.status}
                    disabled={busyId === item.id}
                    onChange={(status) => change.mutate({ id: item.id, status })}
                  />
                  <button
                    type="button"
                    disabled={busyId === item.id}
                    onClick={() => archive.mutate(item.id)}
                    className="self-start py-2 text-xs text-neutral-500 underline disabled:opacity-40"
                  >
                    Togli dalla dispensa
                  </button>
                  {failedId === item.id && (
                    <p role="alert" className="text-sm text-red-600">
                      Non sono riuscito a salvare la modifica. Riprova.
                    </p>
                  )}
                </li>
              ))}
            </ul>
          </section>
        ))}
    </div>
  );
}

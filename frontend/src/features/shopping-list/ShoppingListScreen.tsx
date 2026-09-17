import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AddItemField } from "./AddItemField";
import { addShoppingItem, fetchShoppingList, patchShoppingItem } from "./api";
import { Alert } from "../../components/ui/Alert";
import { Card } from "../../components/ui/Card";
import { SectionEntryCard } from "../../components/ui/SectionEntryCard";
import { SectionHeading } from "../../components/ui/SectionHeading";
import type { ShoppingItem } from "../../domain/types";

// Parziale e tipizzato sull'unione: "manual" non ha nota perché non c'è niente da
// spiegare, e il giorno in cui il backend aggiunge un motivo il compilatore lo dice.
const REASON_HINT: Partial<Record<ShoppingItem["reason"], string>> = {
  finished_while_cooking: "rientrata perché finita cucinando",
  low_while_cooking: "rientrata perché quasi finita cucinando",
};

const UNSORTED = "senza reparto";

function groupByCategory(items: ShoppingItem[]): [string, ShoppingItem[]][] {
  const groups = new Map<string, ShoppingItem[]>();
  for (const item of items) {
    const key = item.ingredient_category ?? UNSORTED;
    groups.set(key, [...(groups.get(key) ?? []), item]);
  }
  // il reparto ignoto va in fondo: sono le voci da chiarire
  return [...groups.entries()].sort(([a], [b]) =>
    a === UNSORTED ? 1 : b === UNSORTED ? -1 : a.localeCompare(b)
  );
}

export function ShoppingListScreen() {
  const queryClient = useQueryClient();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["shopping-list"],
    queryFn: () => fetchShoppingList(),
  });
  const items = data ?? [];

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["shopping-list"] });
  const add = useMutation({
    mutationFn: ({ text, id }: { text: string; id?: string }) => addShoppingItem(text, id),
    onSuccess: invalidate,
  });
  // quale voce ha rifiutato l'ultima scrittura. Il messaggio va accanto a quella
  // voce e non in cima: la lista si scorre mentre si cammina per i reparti, e un
  // avviso fuori schermo non è un avviso (stessa scelta di PantryScreen)
  const [failedId, setFailedId] = useState<string | null>(null);

  const toggle = useMutation({
    mutationFn: (item: ShoppingItem) =>
      patchShoppingItem(item.id, {
        status: item.status === "checked" ? "pending" : "checked",
      }),
    onMutate: () => setFailedId(null),
    onSuccess: invalidate,
    // senza questo una PATCH fallita non dice niente: la casella torna da sé al
    // valore del server e chi guarda resta convinto di aver spuntato
    onError: (_error, item) => setFailedId(item.id),
  });

  // Archiviare è l'unico modo di togliere una voce: «pomdoro» scritto per sbaglio
  // non si cancella spuntandolo, perché spuntarlo lo fa entrare in dispensa — cioè
  // sporca la dispensa per pulire la lista. `fetchShoppingList` chiede solo
  // `pending` e `checked`, quindi la riga sparisce senza altro lavoro.
  const archive = useMutation({
    mutationFn: (id: string) => patchShoppingItem(id, { status: "archived" }),
    onMutate: () => setFailedId(null),
    onSuccess: invalidate,
    onError: (_error, id) => setFailedId(id),
  });

  // due PATCH sulla stessa riga arrivano in ordine ignoto e l'ultima a rispondere
  // vince: spuntare mentre l'archiviazione è in volo è proprio il caso in cui il
  // risultato dipenderebbe dalla rete
  const busyId = toggle.isPending
    ? toggle.variables.id
    : archive.isPending
      ? archive.variables
      : null;

  const checkedCount = items.filter((i) => i.status === "checked").length;

  return (
    <div>
      <div className="px-4 pt-5">
        <h1 className="text-2xl font-semibold tracking-tight">Lista</h1>
      </div>

      <AddItemField onAdd={(text, id) => add.mutateAsync({ text, id })} />

      {/* sempre presente, anche a zero spuntate: «sistema la spesa» è una
          sottosezione, non un avviso. Vedi D3 in docs/prossimi-passi.md */}
      <div className="px-4 pb-1">
        <SectionEntryCard
          to="/sistema"
          title="Sistema la spesa"
          note={
            // finché la lista non è arrivata — e dopo un errore — non si dice
            // niente sul suo contenuto: `items` nasce vuoto, e «niente di
            // spuntato» sarebbe la stessa bugia che due righe sotto ci si vieta.
            // Stessa forma della gemella in PantryScreen: nota generica, strada
            // aperta (D3/CLAUDE.md, «mai un vicolo cieco»)
            isError || data === undefined
              ? "Metti via quello che hai comprato"
              : checkedCount === 0
                ? "Niente di spuntato, per ora"
                : checkedCount === 1
                  ? "1 voce spuntata da mettere via"
                  : `${checkedCount} voci spuntate da mettere via`
          }
          pending={checkedCount > 0}
        />
      </div>

      {isLoading && <p className="px-4 py-3 text-ink-soft">Carico…</p>}
      {/* un caricamento fallito non è una lista vuota: dirlo sarebbe una bugia su
          quello che c'è da comprare. Scrivere resta possibile in entrambi i casi */}
      {isError && (
        <Alert className="px-4 py-3">
          Non sono riuscito a caricare la lista. Puoi comunque aggiungere voci.
        </Alert>
      )}
      {!isLoading && !isError && items.length === 0 && (
        <p className="px-4 py-3 text-ink-soft">Lista vuota. Scrivi cosa ti serve.</p>
      )}

      {groupByCategory(items).map(([category, group]) => (
        <section key={category} className="px-4">
          <SectionHeading>{category}</SectionHeading>
          {/* una scheda per reparto, righe divise da una linea: trenta schede
              separate su uno schermo da 375px sono tutto bordo e niente lista */}
          <Card pad={false}>
            <ul className="divide-y divide-line">
              {group.map((item) => (
                <li key={item.id} className="flex flex-col">
                  <div className="flex items-center gap-3 pl-3">
                    <input
                      type="checkbox"
                      aria-label={item.ingredient_name ?? item.raw_text}
                      checked={item.status === "checked"}
                      disabled={busyId === item.id}
                      onChange={() => toggle.mutate(item)}
                      className="size-5 shrink-0"
                    />
                    <span
                      className={`flex-1 py-3 ${
                        item.status === "checked" ? "text-ink-faint line-through" : ""
                      }`}
                    >
                      {item.raw_text}
                    </span>
                    {/* visibile, non un tooltip: da telefono non esiste il passaggio del
                        mouse, e il motivo per cui una voce è rientrata va letto */}
                    {REASON_HINT[item.reason] && (
                      <span className="shrink-0 text-xs text-low">
                        {REASON_HINT[item.reason]}
                      </span>
                    )}
                    {/* il nome sta nell'etichetta accessibile e non sullo schermo: su
                        375px una riga per voce è quel che rende la lista leggibile
                        camminando, e un bersaglio da pollice ci sta comunque */}
                    <button
                      type="button"
                      aria-label={`Togli ${item.raw_text} dalla lista`}
                      disabled={busyId === item.id}
                      onClick={() => archive.mutate(item.id)}
                      className="min-h-11 shrink-0 px-3 text-lg leading-none text-ink-faint disabled:opacity-40"
                    >
                      ✕
                    </button>
                  </div>
                  {failedId === item.id && (
                    <Alert className="px-3 pb-2">
                      Non sono riuscito a salvare la modifica. La voce è ancora qui: riprova.
                    </Alert>
                  )}
                </li>
              ))}
            </ul>
          </Card>
        </section>
      ))}
    </div>
  );
}

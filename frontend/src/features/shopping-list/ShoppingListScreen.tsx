import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { AddItemField } from "./AddItemField";
import { addShoppingItem, fetchShoppingList, patchShoppingItem } from "./api";
import type { ShoppingItem } from "../../domain/types";

const REASON_HINT: Record<string, string> = {
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
  const { data: items = [], isLoading } = useQuery({
    queryKey: ["shopping-list"],
    queryFn: () => fetchShoppingList(),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["shopping-list"] });
  const add = useMutation({
    mutationFn: ({ text, id }: { text: string; id?: string }) => addShoppingItem(text, id),
    onSuccess: invalidate,
  });
  const toggle = useMutation({
    mutationFn: (item: ShoppingItem) =>
      patchShoppingItem(item.id, {
        status: item.status === "checked" ? "pending" : "checked",
      }),
    onSuccess: invalidate,
  });

  const checkedCount = items.filter((i) => i.status === "checked").length;

  return (
    <div>
      <AddItemField onAdd={(text, id) => add.mutate({ text, id })} />

      {checkedCount > 0 && (
        <div className="px-4 pb-2">
          <Link
            to="/sistema"
            className="block rounded-lg bg-emerald-700 px-4 py-3 text-center text-white"
          >
            Sistema la spesa
          </Link>
        </div>
      )}

      {isLoading && <p className="p-4 text-neutral-500">Carico…</p>}
      {!isLoading && items.length === 0 && (
        <p className="p-4 text-neutral-500">Lista vuota. Scrivi cosa ti serve.</p>
      )}

      {groupByCategory(items).map(([category, group]) => (
        <section key={category} className="px-4 pb-4">
          <h2 className="py-2 text-xs uppercase tracking-wide text-neutral-400">{category}</h2>
          <ul className="divide-y divide-neutral-100">
            {group.map((item) => (
              <li key={item.id} className="flex items-center gap-3 py-3">
                <input
                  type="checkbox"
                  aria-label={item.ingredient_name ?? item.raw_text}
                  checked={item.status === "checked"}
                  onChange={() => toggle.mutate(item)}
                  className="size-5"
                />
                <span className={item.status === "checked" ? "text-neutral-400 line-through" : ""}>
                  {item.raw_text}
                </span>
                {REASON_HINT[item.reason] && (
                  <span title={REASON_HINT[item.reason]} aria-hidden className="text-xs">↩</span>
                )}
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

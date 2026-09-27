import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { searchIngredients } from "../shopping-list/api";
import { searchProducts } from "../stocking/api";
import { useDebounced } from "../../hooks/useDebounced";
import { Alert } from "../../components/ui/Alert";
import { Card } from "../../components/ui/Card";
import { Screen } from "../../components/ui/Screen";
import { SectionHeading } from "../../components/ui/SectionHeading";

const DEBOUNCE_MS = 180;

type ResultItem = { key: string; to: string; title: string; note: string | null };

function Results({
  status,
  items,
  empty,
  failed,
}: {
  status: "pending" | "error" | "success";
  items: ResultItem[];
  empty: string;
  failed: string;
}) {
  if (status === "error") return <Alert>{failed}</Alert>;
  if (status === "pending") return <p className="px-1 text-sm text-ink-soft">Cerco…</p>;
  if (items.length === 0) return <p className="px-1 text-sm text-ink-soft">{empty}</p>;
  return (
    <Card pad={false}>
      <ul className="divide-y divide-line">
        {items.map((item) => (
          <li key={item.key}>
            <Link to={item.to} className="flex min-h-12 items-baseline gap-3 px-3 py-2.5">
              <span className="min-w-0 truncate font-medium">{item.title}</span>
              {item.note && (
                <span className="ml-auto shrink-0 text-xs text-ink-faint">{item.note}</span>
              )}
            </Link>
          </li>
        ))}
      </ul>
    </Card>
  );
}

/** «Anagrafica» (spec S9 §6.2): la porta per quel che in dispensa non c'è.
 *
 * Un campo, le due ricerche che esistono già, due gruppi. Nessun filtro sul `kind`: in
 * anagrafica si corregge anche il detersivo. Senza tasto indietro: ci si arriva
 * dall'hamburger, da qualunque schermata, e non ha una sezione madre.
 */
export function RegistryScreen() {
  const [term, setTerm] = useState("");
  const debounced = useDebounced(term, DEBOUNCE_MS).trim();
  const ready = debounced.length >= 2;
  // sul testo corrente e non su quello ritardato: svuotando il campo i gruppi
  // spariscono subito, come l'elenco di IngredientPicker
  const showing = term.trim().length >= 2;

  // le stesse chiavi di IngredientPicker e di CatalogSearchPanel: è la stessa domanda
  // allo stesso server, e una seconda chiave per la stessa risposta la chiederebbe due
  // volte
  const ingredients = useQuery({
    queryKey: ["ingredients", debounced, "tutti"],
    queryFn: () => searchIngredients(debounced),
    enabled: ready,
  });
  const products = useQuery({
    queryKey: ["products", debounced],
    queryFn: () => searchProducts(debounced),
    enabled: ready,
  });

  return (
    <Screen
      title="Anagrafica"
      subtitle="Ingredienti e prodotti, per correggere quel che è stato registrato male."
    >
      <label className="block text-sm font-medium text-ink-soft">
        Cerca
        <input
          aria-label="Cerca in anagrafica"
          value={term}
          onChange={(event) => setTerm(event.target.value)}
          placeholder="pomodoro, Fage…"
          className="mt-1.5"
        />
      </label>

      {!showing && (
        <p className="pt-3 text-sm text-ink-soft">
          Qui c'è ogni ingrediente e ogni prodotto registrato, anche quel che in dispensa
          non c'è. Aprilo per rinominarlo, cambiargli reparto, spostarlo sotto un altro
          ingrediente o unire un doppione.
        </p>
      )}

      {showing && (
        <>
          <SectionHeading>Ingredienti</SectionHeading>
          <Results
            status={ingredients.status}
            items={(ingredients.data ?? []).map((ingredient) => ({
              key: ingredient.id,
              to: `/anagrafica/ingrediente/${ingredient.id}`,
              title: ingredient.display_name,
              note: ingredient.category,
            }))}
            empty="Nessun ingrediente con questo nome."
            failed="La ricerca degli ingredienti non risponde. Riprova tra poco: niente è cambiato."
          />
          <SectionHeading>Prodotti</SectionHeading>
          <Results
            status={products.status}
            items={(products.data ?? []).map((product) => ({
              key: product.id,
              to: `/anagrafica/prodotto/${product.id}`,
              title: product.name,
              note: product.brand,
            }))}
            empty="Nessun prodotto con questo nome."
            failed="La ricerca dei prodotti non risponde. Riprova tra poco: niente è cambiato."
          />
        </>
      )}
    </Screen>
  );
}

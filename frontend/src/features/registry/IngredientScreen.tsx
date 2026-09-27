import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { ApiError } from "../../api/client";
import { Alert } from "../../components/ui/Alert";
import { Card } from "../../components/ui/Card";
import { Screen } from "../../components/ui/Screen";
import { SectionHeading } from "../../components/ui/SectionHeading";
import { buttonClasses } from "../../components/ui/buttonClasses";
import { AliasRow } from "./AliasRow";
import { CategoryForm } from "./CategoryForm";
import { fetchIngredientDetail } from "./api";
import { backFrom, originFrom, productPath } from "./origin";
import { usageText } from "./wording";

/** La scheda dell'ingrediente (spec S9 §6.3).
 *
 * `key` sull'id: passando da una scheda all'altra — la fusione porta al vincitore, un
 * link porta a un altro ingrediente — React Router riusa lo stesso componente, e senza
 * la chiave la scheda nuova erediterebbe il pannello aperto della precedente. */
export function IngredientScreen() {
  const { id = "" } = useParams();
  return <IngredientCard key={id} id={id} />;
}

type Panel = { kind: "category" };

/** Prima dice cos'è e dove è usato — il peso di una correzione si vede prima di farla —
 * poi gli alias e i prodotti. Le correzioni stanno sopra, e vengono dal servizio unico
 * dell'anagrafica: lo schermo le chiede e mostra il rifiuto con il suo passo dopo. */
function IngredientCard({ id }: { id: string }) {
  const [params] = useSearchParams();
  const origin = originFrom(params.get("da"));
  const back = backFrom(origin);

  const {
    data: ingredient,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["registry", "ingredient", id],
    queryFn: () => fetchIngredientDetail(id),
  });

  // un pannello solo alla volta: due moduli aperti su una scheda del telefono
  // spingerebbero l'altro fuori schermo
  const [panel, setPanel] = useState<Panel | null>(null);

  if (isLoading) {
    return (
      <Screen title="Ingrediente" back={back}>
        <p className="text-ink-soft">Carico…</p>
      </Screen>
    );
  }

  if (isError || !ingredient) {
    // un ingrediente unito a un altro sparisce: un link vecchio porta qui, e «riprova»
    // non potrebbe mai riuscire
    const gone = error instanceof ApiError && error.status === 404;
    return (
      <Screen title="Ingrediente" back={back}>
        <Alert>
          {gone
            ? "Questo ingrediente non c'è più: forse è stato unito a un altro. Cercalo in anagrafica."
            : "Non sono riuscito a leggere questo ingrediente."}
        </Alert>
        {!gone && (
          <button
            type="button"
            onClick={() => void refetch()}
            className={`${buttonClasses("secondary")} mt-3`}
          >
            Riprova
          </button>
        )}
      </Screen>
    );
  }

  return (
    <Screen
      title={ingredient.display_name}
      subtitle={`${ingredient.category} · ${usageText(ingredient.usage)}`}
      back={back}
    >
      <div className="flex flex-wrap gap-2 pb-1">
        <button
          type="button"
          onClick={() => setPanel({ kind: "category" })}
          className={buttonClasses("secondary")}
        >
          Cambia reparto
        </button>
      </div>
      {panel?.kind === "category" && (
        <CategoryForm ingredient={ingredient} onDone={() => setPanel(null)} />
      )}

      <SectionHeading>Alias</SectionHeading>
      {ingredient.aliases.length === 0 ? (
        <p className="px-1 text-sm text-ink-soft">Nessun alias: si trova solo col suo nome.</p>
      ) : (
        <Card pad={false}>
          <ul className="divide-y divide-line px-3">
            {ingredient.aliases.map((alias) => (
              <AliasRow key={alias.id} ingredientId={ingredient.id} alias={alias} />
            ))}
          </ul>
        </Card>
      )}

      <SectionHeading>Prodotti</SectionHeading>
      {ingredient.products.length === 0 ? (
        <p className="px-1 text-sm text-ink-soft">Nessun prodotto sotto questo ingrediente.</p>
      ) : (
        <Card pad={false}>
          <ul className="divide-y divide-line">
            {ingredient.products.map((product) => (
              <li key={product.id}>
                <Link
                  to={productPath(product.id, origin)}
                  className="flex min-h-12 items-baseline gap-2 px-3 py-2.5"
                >
                  <span className="min-w-0 truncate font-medium">{product.name}</span>
                  {product.brand && (
                    <span className="ml-auto shrink-0 text-sm text-ink-faint">{product.brand}</span>
                  )}
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </Screen>
  );
}

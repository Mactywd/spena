import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useLocation, useParams, useSearchParams } from "react-router-dom";
import { ApiError } from "../../api/client";
import { Alert } from "../../components/ui/Alert";
import { Card } from "../../components/ui/Card";
import { Screen } from "../../components/ui/Screen";
import { SectionHeading } from "../../components/ui/SectionHeading";
import { buttonClasses } from "../../components/ui/buttonClasses";
import type { Ingredient, MergeCounts } from "../../domain/types";
import { AliasRow } from "./AliasRow";
import { CategoryForm } from "./CategoryForm";
import { MergePanel } from "./MergePanel";
import { RenameForm } from "./RenameForm";
import { fetchIngredientDetail } from "./api";
import { backFrom, originFrom, productPath } from "./origin";
import { aliasVanishedText, mergeDoneText, usageText } from "./wording";

/** La scheda dell'ingrediente (spec S9 §6.3).
 *
 * `key` sull'id: passando da una scheda all'altra — la fusione porta al vincitore, un
 * link porta a un altro ingrediente — React Router riusa lo stesso componente, e senza
 * la chiave la scheda nuova erediterebbe il pannello aperto della precedente. */
export function IngredientScreen() {
  const { id = "" } = useParams();
  return <IngredientCard key={id} id={id} />;
}

type Panel =
  | { kind: "rename" }
  | { kind: "category" }
  | { kind: "merge"; winner: Ingredient | null };

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

  // sta qui e non dentro AliasRow: l'invalidazione dopo lo spostamento fa sparire
  // quella riga dall'elenco (il server non la manda più), e uno stato suo
  // sparirebbe con lei — la stessa sparizione muta di prima, solo un giro più tardi
  const [vanishedAliasNote, setVanishedAliasNote] = useState<string | null>(null);

  // l'esito di una fusione arriva con la navigazione, dalla scheda del perdente che non
  // c'è più: è qui, sulla scheda del vincitore, che si dice (spec §6.3)
  const location = useLocation();
  const merged = (location.state as { merged?: MergeCounts } | null)?.merged ?? null;

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
      {merged && (
        <p role="status" className="pb-2 text-sm font-medium text-brand">
          {mergeDoneText(merged)}
        </p>
      )}
      <div className="flex flex-wrap gap-2 pb-1">
        <button
          type="button"
          onClick={() => setPanel({ kind: "rename" })}
          className={buttonClasses("secondary")}
        >
          Rinomina
        </button>
        <button
          type="button"
          onClick={() => setPanel({ kind: "category" })}
          className={buttonClasses("secondary")}
        >
          Cambia reparto
        </button>
        <button
          type="button"
          onClick={() => setPanel({ kind: "merge", winner: null })}
          className={buttonClasses("secondary")}
        >
          Unisci a un altro…
        </button>
      </div>
      {panel?.kind === "rename" && (
        <RenameForm
          ingredient={ingredient}
          onDone={() => setPanel(null)}
          onMergeWith={(existing) => setPanel({ kind: "merge", winner: existing })}
        />
      )}
      {panel?.kind === "category" && (
        <CategoryForm ingredient={ingredient} onDone={() => setPanel(null)} />
      )}
      {panel?.kind === "merge" && (
        <MergePanel
          key={panel.winner?.id ?? "da-scegliere"}
          ingredient={ingredient}
          initialWinner={panel.winner}
          origin={origin}
          onClose={() => setPanel(null)}
          onChangeCategory={() => setPanel({ kind: "category" })}
        />
      )}

      <SectionHeading>Alias</SectionHeading>
      {vanishedAliasNote && (
        <p role="status" className="px-1 pb-1 text-sm text-low">
          {vanishedAliasNote}
        </p>
      )}
      {ingredient.aliases.length === 0 ? (
        <p className="px-1 text-sm text-ink-soft">Nessun alias: si trova solo col suo nome.</p>
      ) : (
        <Card pad={false}>
          <ul className="divide-y divide-line px-3">
            {ingredient.aliases.map((alias) => (
              <AliasRow
                key={alias.id}
                ingredientId={ingredient.id}
                alias={alias}
                onVanished={(text, targetName) => setVanishedAliasNote(aliasVanishedText(text, targetName))}
              />
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

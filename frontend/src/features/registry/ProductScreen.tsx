import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { ApiError } from "../../api/client";
import { IngredientPicker } from "../../components/IngredientPicker";
import { Alert } from "../../components/ui/Alert";
import { Card } from "../../components/ui/Card";
import { Screen } from "../../components/ui/Screen";
import { SectionHeading } from "../../components/ui/SectionHeading";
import { buttonClasses } from "../../components/ui/buttonClasses";
import type { Ingredient } from "../../domain/types";
import { InlineField } from "./InlineField";
import {
  fetchProductDetail,
  patchProduct,
  refreshAfterCorrection,
  type ProductPatchBody,
} from "./api";
import { backFrom, ingredientPath, originFrom } from "./origin";
import { movedText, pantryText } from "./wording";

/** La scheda del prodotto (spec S9 §6.4). È anche la scheda dell'elemento di dispensa:
 * dalla riga della dispensa si arriva qui, e l'ingrediente sta come link. Il caso del
 * parmigiano sotto «burro» sono due tocchi e una scelta.
 *
 * `key` sull'id, per la stessa ragione della scheda dell'ingrediente. */
export function ProductScreen() {
  const { id = "" } = useParams();
  return <ProductCard key={id} id={id} />;
}

function ProductCard({ id }: { id: string }) {
  const [params] = useSearchParams();
  const origin = originFrom(params.get("da"));
  const back = backFrom(origin);
  const queryClient = useQueryClient();
  const [moving, setMoving] = useState(false);
  const [movedNote, setMovedNote] = useState<string | null>(null);

  const {
    data: product,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["registry", "product", id],
    queryFn: () => fetchProductDetail(id),
  });
  const patch = useMutation({
    mutationFn: (body: ProductPatchBody) => patchProduct(id, body),
    onSuccess: () => refreshAfterCorrection(queryClient),
  });
  const move = useMutation({
    mutationFn: (target: Ingredient) => patchProduct(id, { ingredient_id: target.id }),
    onSuccess: async (updated) => {
      setMoving(false);
      setMovedNote(movedText(updated));
      await refreshAfterCorrection(queryClient);
    },
  });

  if (isLoading) {
    return (
      <Screen title="Prodotto" back={back}>
        <p className="text-ink-soft">Carico…</p>
      </Screen>
    );
  }

  if (isError || !product) {
    const gone = error instanceof ApiError && error.status === 404;
    return (
      <Screen title="Prodotto" back={back}>
        <Alert>
          {gone
            ? "Questo prodotto non c'è più. Gli elementi di dispensa che lo avevano sono rimasti, sfusi."
            : "Non sono riuscito a leggere questo prodotto."}
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
    <Screen title={product.name} subtitle={product.brand ?? undefined} back={back}>
      {movedNote && (
        <p role="status" className="pb-2 text-sm font-medium text-brand">
          {movedNote}
        </p>
      )}

      <Card className="flex flex-col gap-3">
        {/* obbligatorio (F17): il nome non può restare nullo in colonna */}
        <InlineField
          label="Nome"
          value={product.name}
          required
          onSave={(next) => patch.mutateAsync({ name: next })}
        />
        {/* non obbligatoria: una marca vuota è una richiesta valida, toglierla */}
        <InlineField
          label="Marca"
          value={product.brand ?? ""}
          placeholder="Nessuna marca"
          onSave={(next) => patch.mutateAsync({ brand: next === "" ? null : next })}
        />
      </Card>

      <SectionHeading>Ingrediente</SectionHeading>
      <Card className="flex flex-col gap-2">
        <Link
          to={ingredientPath(product.ingredient.id, origin)}
          className="inline-flex min-h-11 items-center font-medium text-brand"
        >
          {product.ingredient.display_name}
        </Link>
        <div className="flex flex-wrap items-center gap-2 text-sm text-ink-soft">
          <span>È sotto l'ingrediente sbagliato?</span>
          <button
            type="button"
            aria-expanded={moving}
            onClick={() => setMoving((open) => !open)}
            className={buttonClasses("secondary")}
          >
            Spostalo
          </button>
        </div>
        {/* senza filtro sul `kind`: in anagrafica si corregge anche il non alimentare */}
        {moving && (
          <IngredientPicker
            label="Sposta sotto"
            failureNote="Il prodotto resta dov'è: riprova tra poco."
            disabled={move.isPending}
            onPick={(target) => move.mutate(target)}
          />
        )}
        {move.isError && (
          <Alert>
            Non sono riuscito a spostarlo: è ancora sotto «{product.ingredient.display_name}». Riprova.
          </Alert>
        )}
        <p className="text-xs text-ink-faint">{pantryText(product.pantry_items.length)}</p>
      </Card>
    </Screen>
  );
}

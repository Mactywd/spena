import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Alert } from "../../components/ui/Alert";
import { Card } from "../../components/ui/Card";
import { buttonClasses } from "../../components/ui/buttonClasses";
import { FOOD_CATEGORIES, NON_FOOD_CATEGORIES } from "../../domain/categories";
import type { IngredientDetail } from "../../domain/types";
import { patchIngredient, refreshAfterCorrection, registryRefusal } from "./api";

/** «Cambia reparto» (spec §6.3). Tutti i reparti, i non alimentari compresi: in
 * anagrafica si corregge anche il detersivo creato in «latticini». Il rifiuto per le
 * ricette le elenca, ciascuna col suo link — è da lì che si toglie l'ingrediente, se
 * davvero non è cibo (spec §7). */
export function CategoryForm({
  ingredient,
  onDone,
}: {
  ingredient: IngredientDetail;
  onDone: () => void;
}) {
  const queryClient = useQueryClient();
  const [category, setCategory] = useState(ingredient.category);
  const save = useMutation({
    mutationFn: (next: string) => patchIngredient(ingredient.id, { category: next }),
    onSuccess: async () => {
      await refreshAfterCorrection(queryClient);
      onDone();
    },
  });
  const refusal = registryRefusal(save.error);

  return (
    <Card as="section" className="mt-2 flex flex-col gap-3">
      <label className="text-sm font-medium text-ink-soft">
        Reparto
        <select
          value={category}
          onChange={(event) => setCategory(event.target.value)}
          disabled={save.isPending}
          className="mt-1.5"
        >
          {FOOD_CATEGORIES.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
          {/* staccati, come in «Sistema la spesa»: non sono un reparto in più, sono la
              metà dell'anagrafica che le ricette non vedono */}
          <optgroup label="Non alimentari">
            {NON_FOOD_CATEGORIES.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </optgroup>
        </select>
      </label>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={save.isPending || category === ingredient.category}
          onClick={() => save.mutate(category)}
          className={buttonClasses("primary")}
        >
          Salva il reparto
        </button>
        <button type="button" onClick={onDone} className={buttonClasses("ghost")}>
          Lascia com'è
        </button>
      </div>
      {refusal?.code === "non_food_in_recipes" && (
        <div role="alert" className="flex flex-col gap-1 text-sm">
          <p className="text-danger">{refusal.detail}</p>
          {refusal.recipes.length > 0 && (
            <ul>
              {refusal.recipes.map((recipe) => (
                <li key={recipe.id}>
                  <Link
                    to={`/ricette/${recipe.id}`}
                    className="inline-flex min-h-11 items-center font-medium text-brand"
                  >
                    {recipe.title}
                  </Link>
                </li>
              ))}
            </ul>
          )}
          {refusal.recipe_count > refusal.recipes.length && (
            <p className="text-ink-soft">e altre {refusal.recipe_count - refusal.recipes.length}.</p>
          )}
          {/* Le ricette dell'import in attesa non hanno ancora una pagina da aprire: il
              passo è la decisione che le lega qui, e quei termini sono gli alias
              «Deciso nella coda» di questa scheda, ciascuno col suo link. */}
          {refusal.pending_import_count > 0 && (
            <>
              <p className="text-ink-soft">
                I termini dell'import decisi qui sono fra gli alias qui sotto, segnati «Deciso
                nella coda».
              </p>
              <Link
                to="/ricette/importa"
                className="inline-flex min-h-11 items-center font-medium text-brand"
              >
                Vai a «Ingredienti da abbinare»
              </Link>
            </>
          )}
        </div>
      )}
      {refusal !== null && refusal.code !== "non_food_in_recipes" && <Alert>{refusal.detail}</Alert>}
      {save.isError && refusal === null && (
        <Alert>
          Non sono riuscito a cambiare il reparto. È ancora «{ingredient.category}»: riprova.
        </Alert>
      )}
    </Card>
  );
}

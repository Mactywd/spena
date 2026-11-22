import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { BackLink } from "../../components/BackLink";
import { ErrorState } from "../../components/ui/ErrorState";
import { useNotice } from "../../components/ui/noticeContext";
import { createRecipe } from "../recipes/api";
import { RecipeForm } from "../recipe-form/RecipeForm";
import { EMPTY_FORM } from "../recipe-form/formModel";
import { MEALS_KEY, fetchMeal } from "./api";

/** `/pasti/:id/ricetta/nuova`: il modulo di sempre per scrivere la ricetta di un pasto.
 * Parte col titolo uguale al piatto e 1 porzione (le dosi di come lo si mangia); la
 * ricetta nasce fuori dal ricettario, legata al pasto (`meal_id`). */
export function MealRecipeNewScreen() {
  const { id = "" } = useParams();
  const meal = useQuery({ queryKey: [...MEALS_KEY, "meal", id], queryFn: () => fetchMeal(id) });
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const notice = useNotice();
  const [values, setValues] = useState<typeof EMPTY_FORM | null>(null);

  const back = <BackLink to={`/pasti/${id}`} label="Pasto" />;
  if (meal.isError) {
    return (
      <div className="px-4 pt-2">
        {back}
        <ErrorState
          message="Il pasto non si carica."
          onRetry={() => meal.refetch()}
          retrying={meal.isFetching}
        />
      </div>
    );
  }
  if (!meal.data) return <p className="px-4 pt-5 text-sm text-ink-soft">Carico il pasto…</p>;
  // una volta sola, dal piatto caricato: una rilettura non cancella quel che si scrive
  const current = values ?? { ...EMPTY_FORM, title: meal.data.dish, servingsText: "1" };

  return (
    <div className="px-4 pb-4 pt-2">
      {back}
      <h1 className="text-2xl font-semibold tracking-tight">Scrivi la ricetta</h1>
      <p className="pb-3 text-sm text-ink-soft">
        Resta fuori dal ricettario finché non la salvi lì.
      </p>
      <RecipeForm
        values={current}
        onChange={(update) =>
          setValues((prev) =>
            typeof update === "function" ? update(prev ?? current) : update
          )
        }
        save={(body) =>
          createRecipe({ ...body, source: "manual", source_ref: null, meal_id: id })
        }
        onSaved={(saved) => {
          void queryClient.invalidateQueries({ queryKey: MEALS_KEY });
          void queryClient.invalidateQueries({ queryKey: ["recipe", saved.id] });
          notice({ text: "Salvata." });
          navigate(`/pasti/${id}`, { replace: true });
        }}
        submitLabel="Salva la ricetta"
      />
    </div>
  );
}

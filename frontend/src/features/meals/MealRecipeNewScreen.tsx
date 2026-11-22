import { useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError } from "../../api/client";
import { BackLink } from "../../components/BackLink";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { buttonClasses } from "../../components/ui/buttonClasses";
import { ErrorState } from "../../components/ui/ErrorState";
import { useNotice } from "../../components/ui/noticeContext";
import type { RecipeBody } from "../../domain/types";
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
  // l'ultimo corpo mandato: se intanto è arrivata la ricetta di Claude, è quel che si salva a parte
  const lastBody = useRef<RecipeBody | null>(null);
  const [arrived, setArrived] = useState(false);
  const [keepError, setKeepError] = useState<string | null>(null);
  const [keeping, setKeeping] = useState(false);

  async function keepInBook() {
    if (!lastBody.current) return;
    setKeeping(true);
    setKeepError(null);
    try {
      const saved = await createRecipe({
        ...lastBody.current,
        source: "manual",
        source_ref: null,
        meal_id: null,
      });
      void queryClient.invalidateQueries({ queryKey: MEALS_KEY });
      void queryClient.invalidateQueries({ queryKey: ["recipes"] });
      void queryClient.invalidateQueries({ queryKey: ["recipe", saved.id] });
      notice({ text: "Salvata nel ricettario." });
      navigate(`/ricette/${saved.id}`, { replace: true });
    } catch (err) {
      const detail =
        err instanceof ApiError
          ? (err.body as { detail?: unknown } | null)?.detail
          : null;
      setKeepError(
        typeof detail === "string"
          ? detail
          : "Non sono riuscito a salvarla nel ricettario. Niente è andato perso: riprova.",
      );
      setKeeping(false);
    }
  }

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
        save={async (body) => {
          lastBody.current = body;
          try {
            return await createRecipe({
              ...body,
              source: "manual",
              source_ref: null,
              meal_id: id,
            });
          } catch (err) {
            const code =
              err instanceof ApiError && err.status === 409
                ? (err.body as { code?: unknown } | null)?.code
                : null;
            if (code === "has_recipe") setArrived(true);
            throw err;
          }
        }}
        onSaved={(saved) => {
          void queryClient.invalidateQueries({ queryKey: MEALS_KEY });
          void queryClient.invalidateQueries({ queryKey: ["recipe", saved.id] });
          notice({ text: "Salvata." });
          navigate(`/pasti/${id}`, { replace: true });
        }}
        submitLabel="Salva la ricetta"
      />
      {arrived && (
        <div className="space-y-3 pt-4">
          <Alert tone="note">
            Nel frattempo è arrivata la ricetta di Claude. Quella che hai
            scritto non è persa: puoi salvarla nel ricettario.
          </Alert>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="primary"
              busy={keeping}
              onClick={() => void keepInBook()}
            >
              Salva nel ricettario
            </Button>
            <Link to={`/pasti/${id}`} className={buttonClasses("secondary")}>
              Vedi la ricetta di Claude
            </Link>
          </div>
          {keepError && <Alert>{keepError}</Alert>}
        </div>
      )}
    </div>
  );
}

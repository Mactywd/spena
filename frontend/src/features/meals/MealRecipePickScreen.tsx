import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { ApiError } from "../../api/client";
import { BackLink } from "../../components/BackLink";
import { Alert } from "../../components/ui/Alert";
import { ErrorState } from "../../components/ui/ErrorState";
import { useNotice } from "../../components/ui/noticeContext";
import { useDebounced } from "../../hooks/useDebounced";
import { searchRecipes } from "../recipes/api";
import { MEALS_KEY, copyRecipeToMeal } from "./api";

function problem(error: unknown): string {
  const detail = error instanceof ApiError ? (error.body as { detail?: unknown } | null)?.detail : null;
  if (typeof detail === "string") return detail;
  return "Non sono riuscito a copiare la ricetta. Riprova fra poco.";
}

/** `/pasti/:id/ricetta/scegli`: sceglie una ricetta del ricettario; il pasto ne riceve
 * una copia, quella del ricettario non cambia mai (decisione 4). */
export function MealRecipePickScreen() {
  const { id = "" } = useParams();
  const [query, setQuery] = useState("");
  const debounced = useDebounced(query, 180);
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const notice = useNotice();

  const results = useQuery({
    queryKey: ["recipes", "meal-pick", debounced],
    queryFn: () => searchRecipes({ query: debounced }),
  });
  const copy = useMutation({
    mutationFn: (recipeId: string) => copyRecipeToMeal(id, recipeId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: MEALS_KEY });
      notice({ text: "Ricetta copiata nel pasto." });
      navigate(`/pasti/${id}`, { replace: true });
    },
  });
  const recipes = results.data?.recipes ?? [];

  return (
    <div className="px-4 pb-4 pt-2">
      <BackLink to={`/pasti/${id}`} label="Pasto" />
      <h1 className="text-2xl font-semibold tracking-tight">Scegli dal ricettario</h1>
      <p className="pb-3 text-sm text-ink-soft">
        Il pasto riceve una copia: la ricetta del ricettario non cambia.
      </p>
      <label className="flex flex-col gap-1 text-sm font-medium">
        Cerca nel ricettario
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </label>
      {copy.isError && <Alert className="pt-3">{problem(copy.error)}</Alert>}
      <div className="pt-3">
        {results.isError ? (
          <ErrorState
            message="Non sono riuscito a cercare nel ricettario."
            onRetry={() => results.refetch()}
            retrying={results.isFetching}
          />
        ) : results.isLoading ? (
          <p className="text-sm text-ink-soft">Cerco…</p>
        ) : recipes.length === 0 ? (
          <p className="text-sm text-ink-soft">Nessuna ricetta.</p>
        ) : (
          <ul className="flex flex-col divide-y divide-line">
            {recipes.map((r) => (
              <li key={r.id}>
                <button
                  type="button"
                  disabled={copy.isPending}
                  onClick={() => copy.mutate(r.id)}
                  className="flex min-h-11 w-full flex-col items-start justify-center py-2 text-left"
                >
                  <span className="font-medium">{r.title}</span>
                  {!r.cookable && r.missing_names.length > 0 && (
                    <span className="text-sm text-ink-soft">Manca: {r.missing_names.join(", ")}</span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { fetchRecipe } from "../recipes/api";
import { fetchPantry } from "../pantry/api";
import { CookSheet } from "./CookSheet";
import type { RecipeIngredientLine } from "../../domain/types";

function statusNote(line: RecipeIngredientLine): string {
  if (line.availability === "missing") return "manca";
  if (line.availability === "available") return "disponibile";
  // l'unico caso interessante: quasi finito, dove il ruolo fa la differenza
  return line.satisfied ? "quasi finito, basta" : "quasi finito, non basta";
}

export function RecipeDetailScreen() {
  const { id = "" } = useParams();
  const [cooking, setCooking] = useState(false);

  const {
    data: recipe,
    isLoading: isRecipeLoading,
    isError: isRecipeError,
    refetch: refetchRecipe,
  } = useQuery({
    queryKey: ["recipe", id],
    queryFn: () => fetchRecipe(id),
  });

  // Serve solo per aprire il foglio di cottura: senza dispensa non si può dire
  // quali vasetti esistono, quindi un fallimento qui non può travestirsi da
  // "nessun vasetto da aggiornare" — altrimenti "Cucina" apparirebbe disponibile
  // ma produrrebbe un foglio vuoto, silenziosamente sbagliato.
  const {
    data: pantry,
    isLoading: isPantryLoading,
    isError: isPantryError,
    refetch: refetchPantry,
  } = useQuery({ queryKey: ["pantry"], queryFn: fetchPantry });

  if (isRecipeLoading) return <p className="p-4 text-neutral-500">Carico…</p>;

  // un caricamento fallito non è una ricetta vuota: dirlo sarebbe una bugia su
  // cosa serve e cosa si ha
  if (isRecipeError || !recipe) {
    return (
      <div className="flex flex-col items-start gap-2 p-4">
        <p role="alert" className="text-sm text-red-600">
          Non sono riuscito a caricare questa ricetta. Riprova.
        </p>
        <button
          type="button"
          onClick={() => void refetchRecipe()}
          className="rounded-lg border px-4 py-3 text-sm"
        >
          Riprova
        </button>
      </div>
    );
  }

  const primary = recipe.ingredients.filter((line) => line.role === "primary");
  const secondary = recipe.ingredients.filter((line) => line.role === "secondary");
  const groups: { label: string; lines: RecipeIngredientLine[] }[] = [
    { label: "Principali", lines: primary },
    { label: "Secondari", lines: secondary },
  ];

  return (
    <div className="p-4">
      <h1 className="text-xl font-semibold">{recipe.title}</h1>
      {recipe.description && <p className="text-neutral-500">{recipe.description}</p>}

      {cooking && pantry ? (
        <div className="pt-4">
          <CookSheet recipe={recipe} pantryItems={pantry} onDone={() => setCooking(false)} />
        </div>
      ) : (
        <>
          {groups.map(({ label, lines }) => (
            <section key={label} className="pt-4">
              <h2 className="text-xs uppercase tracking-wide text-neutral-400">{label}</h2>
              <ul className="divide-y divide-neutral-100">
                {lines.map((line) => (
                  <li key={line.ingredient_id} className="flex justify-between gap-2 py-2">
                    <span>
                      {line.ingredient_name}
                      {line.quantity_text && (
                        <span className="ml-2 text-sm text-neutral-400">{line.quantity_text}</span>
                      )}
                    </span>
                    <span
                      className={`shrink-0 text-xs ${
                        line.satisfied ? "text-emerald-700" : "text-amber-700"
                      }`}
                    >
                      {statusNote(line)}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          ))}

          <section className="pt-4">
            <h2 className="text-xs uppercase tracking-wide text-neutral-400">Procedimento</h2>
            <p className="whitespace-pre-line pt-1">{recipe.instructions}</p>
          </section>

          {/* "Cucina" apre il foglio di cottura, che ha bisogno della dispensa per
              elencare i vasetti concreti: senza quella, il pulsante dice perché non
              si può procedere invece di aprire un foglio vuoto e muto */}
          {isPantryError ? (
            <div className="mt-6 flex flex-col items-start gap-2">
              <p role="alert" className="text-sm text-red-600">
                Non sono riuscito a caricare la dispensa: non posso avviare la cottura.
              </p>
              <button
                type="button"
                onClick={() => void refetchPantry()}
                className="rounded-lg border px-4 py-3 text-sm"
              >
                Riprova
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setCooking(true)}
              disabled={isPantryLoading}
              className="mt-6 w-full rounded-lg bg-emerald-700 px-4 py-3 text-white disabled:opacity-40"
            >
              Cucina
            </button>
          )}
        </>
      )}
    </div>
  );
}

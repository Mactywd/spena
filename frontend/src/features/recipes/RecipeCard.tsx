import { Link } from "react-router-dom";
import type { RecipeSummary } from "../../domain/types";

const SOURCE_LABEL: Record<string, string> = {
  dataset: "dataset",
  manual: "scritta da te",
  ai: "AI",
};

// La frase "puoi cucinarla" risponde a `cookable`, che è il verdetto del backend,
// e non a `missing === 0`, che è un altro campo. Dedurre il verdetto da un conteggio
// è il frontend che rifà un calcolo di dominio: oggi i due campi concordano per
// costruzione, ma il giorno in cui la regola cambia la scheda mentirebbe.
function missingLabel(recipe: RecipeSummary): string {
  if (recipe.cookable) return "Puoi cucinarla ora";
  if (recipe.missing === 1) return "manca 1 ingrediente";
  return `mancano ${recipe.missing} ingredienti`;
}

export function RecipeCard({ recipe }: { recipe: RecipeSummary }) {
  return (
    <li className="py-3">
      <Link to={`/ricette/${recipe.id}`} className="block">
        <div className="flex items-baseline justify-between gap-2">
          <span className="font-medium">{recipe.title}</span>
          <span className="shrink-0 text-xs text-neutral-400">
            {SOURCE_LABEL[recipe.source] ?? recipe.source}
          </span>
        </div>
        {recipe.description && (
          <p className="text-sm text-neutral-500">{recipe.description}</p>
        )}
        <p className={`text-xs ${recipe.cookable ? "text-emerald-700" : "text-amber-700"}`}>
          {missingLabel(recipe)}
        </p>
      </Link>
    </li>
  );
}

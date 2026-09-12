import { Link } from "react-router-dom";
import type { RecipeSummary } from "../../domain/types";

const SOURCE_LABEL: Record<string, string> = {
  dataset: "dataset",
  manual: "scritta da te",
  ai: "AI",
};

function missingLabel(missing: number): string {
  if (missing === 0) return "Puoi cucinarla ora";
  if (missing === 1) return "manca 1 ingrediente";
  return `mancano ${missing} ingredienti`;
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
          {missingLabel(recipe.missing)}
        </p>
      </Link>
    </li>
  );
}

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
    <li>
      <Link to={`/ricette/${recipe.id}`} className="block rounded-card bg-card p-3.5">
        <div className="flex items-baseline justify-between gap-2">
          <span className="font-medium">{recipe.title}</span>
          <span className="shrink-0 text-xs text-ink-faint">
            {SOURCE_LABEL[recipe.source] ?? recipe.source}
          </span>
        </div>
        {recipe.description && (
          <p className="pt-0.5 text-sm text-ink-soft">{recipe.description}</p>
        )}
        {/* verde o ambra, gli stessi due colori della dispensa: «puoi cucinarla» e
            «ti manca qualcosa» sono la stessa distinzione di «disponibile» e «quasi
            finito», vista dall'altro capo della stessa regola */}
        <div className="pt-2">
          <span
            className={`inline-block rounded-full px-2.5 py-1 text-xs font-medium ${
              recipe.cookable ? "bg-brand-tint text-brand" : "bg-low-tint text-low"
            }`}
          >
            {missingLabel(recipe)}
          </span>
        </div>
      </Link>
    </li>
  );
}

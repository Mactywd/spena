import type { Ingredient } from "../../domain/types";

// L'elenco dei suggerimenti dell'anagrafica. Ne esistevano due copie identiche — nel
// campo della lista e nel selettore di ingredienti — e due copie della stessa cosa si
// scollano: la prima differenza che compare è sempre la misura del bersaglio.
export function OptionList({
  options,
  onPick,
  disabled = false,
}: {
  options: Ingredient[];
  onPick: (ingredient: Ingredient) => void;
  disabled?: boolean;
}) {
  return (
    <ul role="listbox" className="divide-y divide-line overflow-hidden rounded-card bg-card">
      {options.map((ingredient) => (
        <li key={ingredient.id}>
          <button
            type="button"
            role="option"
            aria-selected={false}
            disabled={disabled}
            onClick={() => onPick(ingredient)}
            className="flex min-h-12 w-full items-baseline gap-3 px-3 py-2.5 text-left text-sm disabled:opacity-50"
          >
            <span className="truncate">{ingredient.display_name}</span>
            {/* la categoria serve a distinguere due omonimi, non a essere letta
                sempre: in fondo alla riga, dove l'occhio passa solo se cerca */}
            <span className="ml-auto shrink-0 text-xs text-ink-faint">{ingredient.category}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}

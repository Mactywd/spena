import { IngredientPicker } from "../../components/IngredientPicker";
import { Button } from "../../components/ui/Button";
import { IconClearAll, IconX } from "../../components/ui/icons";
import type { Ingredient } from "../../domain/types";

/** Il pannello «Filtri» del ricettario (spec T3 §4.5): categoria e ingredienti, quante
 * ricette rispondono, e «Azzera». In linea sotto la barra e non un foglio sopra l'elenco:
 * aperto, si vede ancora cosa cambia sotto.
 *
 * Resta montato anche chiuso (`hidden`): un ingrediente scritto a metà non si perde
 * richiudendolo, e `aria-controls` di «Filtri» punta sempre a un elemento che c'è. La
 * scala non sta qui: è sempre a video, e non conta come filtro. */
export function RecipeFiltersPanel({
  id,
  open,
  categories,
  category,
  onCategory,
  ingredients,
  onPick,
  onRemove,
  count,
  onReset,
}: {
  id: string;
  open: boolean;
  /** le categorie presenti nel ricettario: un filtro che offre voci vuote porta a una
   * schermata vuota */
  categories: string[];
  category: string;
  onCategory: (category: string) => void;
  ingredients: Ingredient[];
  onPick: (ingredient: Ingredient) => void;
  onRemove: (id: string) => void;
  /** «N ricette», «Cerco…», o `null` quando non si sa */
  count: string | null;
  /** assente quando non c'è niente da azzerare: allora «Azzera» non c'è */
  onReset?: () => void;
}) {
  return (
    <div id={id} hidden={!open}>
      <div className="mt-2 flex flex-col gap-3 rounded-2xl bg-card p-3">
        {categories.length > 0 && (
          <label className="text-sm font-medium text-ink-soft">
            Categoria
            <select
              aria-label="Categoria"
              value={category}
              onChange={(e) => onCategory(e.target.value)}
              className="mt-1.5"
            >
              <option value="">Tutte</option>
              {categories.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </label>
        )}

        {/* il campo resta a video anche con qualcosa già scelto: gli ingredienti si
            sommano, e un campo che sparisce al primo tocco direbbe il contrario */}
        <IngredientPicker
          label="Contiene ingredienti"
          failureNote="Puoi comunque cercare per parole qui sopra."
          kind="food"
          onPick={onPick}
        />

        {ingredients.length > 0 && (
          <ul className="flex flex-wrap items-center gap-2">
            {ingredients.map((chosen) => (
              <li
                key={chosen.id}
                className="flex items-center gap-1 rounded-card bg-brand-tint pr-1 pl-3"
              >
                <span className="min-w-0 truncate text-sm text-brand">{chosen.display_name}</span>
                {/* la stessa X con cui si toglie una voce dalla dispensa, e per la stessa
                    ragione il nome accessibile nomina l'ingrediente: su tre pastiglie
                    «Togli» ripetuto identico non dice quale si sta togliendo */}
                <button
                  type="button"
                  aria-label={`Togli il filtro su ${chosen.display_name}`}
                  onClick={() => onRemove(chosen.id)}
                  className="flex size-11 shrink-0 items-center justify-center rounded-full text-brand"
                >
                  <IconX aria-hidden="true" className="size-4" stroke={2} />
                </button>
              </li>
            ))}
          </ul>
        )}

        {(count !== null || onReset) && (
          <div className="flex min-h-11 items-center justify-between gap-3">
            <p className="text-sm text-ink-soft">{count}</p>
            {onReset && (
              <Button variant="ghost" icon={IconClearAll} onClick={onReset}>
                Azzera
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

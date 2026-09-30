import { FOOD_CATEGORIES, NON_FOOD_CATEGORIES } from "../domain/categories";
import { capitalizeFirst } from "../lib/text";

/** Il reparto di un ingrediente (spec T3 §4.7): lo stesso campo per Sistema la spesa,
 * l'Anagrafica, la coda d'import e il modulo della ricetta, che ne avevano quattro copie.
 *
 * `foodOnly` nei posti del mondo ricette — la riga da creare del modulo, il passo «Come
 * si chiama in generale?» quando lo apre il modulo (R12), la scheda della coda d'import:
 * una ricetta non può nominare un non alimentare (`write_recipe_ingredients` lo
 * rifiuta), e offrirlo qui sarebbe offrire un rifiuto un istante dopo. Altrove i non
 * alimentari stanno a parte, in un gruppo loro: non sono un reparto in più del
 * supermercato, sono la metà dell'anagrafica che le ricette non vedono.
 *
 * «Reparto» e non «Categoria»: nel modulo della ricetta «Categoria» è già quella della
 * ricetta (Primi piatti, Dolci). Le voci si leggono con la maiuscola, come i titoli delle
 * sezioni; il valore resta quello del backend (`IngredientCategory`), in minuscolo. */
export function CategorySelect({
  value,
  onChange,
  foodOnly = false,
  label = "Reparto",
  accessibleLabel,
  disabled = false,
}: {
  value: string;
  onChange: (category: string) => void;
  foodOnly?: boolean;
  label?: string;
  /** Quando deve dire più dell'etichetta in vista: in un elenco di righe o di schede,
   * per quale. Di norma coincide con `label`. */
  accessibleLabel?: string;
  disabled?: boolean;
}) {
  return (
    <label className="text-sm font-medium text-ink-soft">
      {label}
      <select
        aria-label={accessibleLabel ?? label}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
        className="mt-1.5"
      >
        {FOOD_CATEGORIES.map((category) => (
          <option key={category} value={category}>
            {capitalizeFirst(category)}
          </option>
        ))}
        {!foodOnly && (
          <optgroup label="Non alimentari">
            {NON_FOOD_CATEGORIES.map((category) => (
              <option key={category} value={category}>
                {capitalizeFirst(category)}
              </option>
            ))}
          </optgroup>
        )}
      </select>
    </label>
  );
}

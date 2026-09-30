import type {
  DraftIngredient,
  Ingredient,
  IngredientRole,
  RecipeBody,
  RecipeDetail,
  RecipeDraft,
  RecipeIngredientBody,
  RecipeIngredientLine,
} from "../../domain/types";

// I limiti che `RecipeFields` applica nel backend. Stanno qui per far correggere un
// campo *prima* della chiamata, non per decidere qualcosa: l'autorità resta il
// backend, e un 422 che arriva comunque viene detto per quello che è.
export const TITLE_MAX = 200;
export const QUANTITY_MAX = 100;
const SERVINGS_MIN = 1;
const SERVINGS_MAX = 50;

/** Una riga di ingrediente del modulo. Le righe della bozza, quelle scelte a mano e
 * quelle di una ricetta già salvata convivono nella stessa lista: cambia solo chi ha
 * proposto l'aggancio, e quello che il backend ha detto di quell'aggancio. */
export interface FormLine {
  key: string;
  label: string;
  ingredientId: string | null;
  matchedName: string | null;
  // vero solo per una riga della bozza che il backend ha marcato `confident: false`.
  // Non lo ricalcoliamo: lo riportiamo.
  uncertain: boolean;
  /** Vero per le righe che non vengono dal modello: scelte a mano, o già nella ricetta
   * salvata. Una bozza nuova le lascia dove sono. */
  manual: boolean;
  role: IngredientRole;
  quantityText: string;
  /** Falso solo per un aggancio incerto non ancora confermato. Le altre righe non si
   * escludono: si tolgono con la ✕ (R10 §6.2). */
  included: boolean;
  // `null` quando la riga è agganciata o quando il modello non ha detto niente di
  // utilizzabile. Valorizzato è la ragione per cui una riga senza aggancio può
  // comunque salvarsi: il modello ha detto cos'è e in che reparto.
  proposedCategory: string | null;
  /** La nota della riga salvata, portata com'è: il modulo non la mostra e non la
   * cambia, ma una modifica non deve perderla. */
  note: string | null;
}

export interface RecipeFormValues {
  title: string;
  description: string;
  category: string | null;
  // stringa, non numero: un campo vuoto vuole dire "non lo so", e non deve diventare
  // uno zero o un 4 inventato da noi
  servingsText: string;
  // `null` è «non indicato»: una ricetta scritta a mano parte senza costo
  cost: number | null;
  instructions: string;
  lines: FormLine[];
}

export const EMPTY_FORM: RecipeFormValues = {
  title: "",
  description: "",
  category: null,
  servingsText: "",
  cost: null,
  instructions: "",
  lines: [],
};

export function lineFromDraft(line: DraftIngredient, index: number): FormLine {
  const attached = line.ingredient_id !== null;
  const uncertain = attached && !line.confident;
  return {
    // l'indice, non il solo nome: niente vieta al modello di proporre due volte lo
    // stesso `raw_name`, e due righe con la stessa chiave si muoverebbero insieme —
    // oltre a far scartare una riga a React senza dire niente
    key: `draft:${index}:${line.raw_name}`,
    label: line.raw_name,
    ingredientId: line.ingredient_id,
    matchedName: line.matched_name,
    uncertain,
    manual: false,
    role: line.role,
    quantityText: line.quantity_text ?? "",
    // Un aggancio incerto parte ESCLUSO. Partire incluso lo farebbe entrare nel
    // ricettario senza che nessuno l'abbia guardato, ed è esattamente l'accettazione
    // in silenzio che la seconda decisione di progetto vieta: un ingrediente sbagliato
    // avvelena la disponibilità di ogni ricetta che lo usa.
    included: !uncertain,
    proposedCategory: attached ? null : line.proposed_category ?? null,
    note: null,
  };
}

export function lineFromIngredient(ingredient: Ingredient): FormLine {
  return {
    key: `manual:${ingredient.id}`,
    label: ingredient.display_name,
    ingredientId: ingredient.id,
    matchedName: ingredient.name,
    uncertain: false,
    manual: true,
    // "principale" è il default prudente: un principale esige disponibilità piena,
    // quindi al massimo fa sembrare la ricetta meno cucinabile di quanto sia — mai il
    // contrario. Il ruolo resta cambiabile sulla riga.
    role: "primary",
    quantityText: "",
    included: true,
    proposedCategory: null,
    note: null,
  };
}

/** R12: una riga per un ingrediente che l'anagrafica non ha, scritta a mano. È fatta
 * come le righe dell'AI non agganciate — nome e reparto, «lo creo io salvando» — e
 * l'ingrediente nasce al salvataggio, dentro la transazione della ricetta
 * (`_resolve_lines` nel backend, per la creazione e per la modifica). `manual`: una
 * bozza nuova dell'AI non la porta via. */
export function lineFromNewName(name: string, category: string): FormLine {
  const label = name.trim();
  return {
    key: `new:${label.toLowerCase()}`,
    label,
    ingredientId: null,
    matchedName: null,
    uncertain: false,
    manual: true,
    role: "primary",
    quantityText: "",
    included: true,
    proposedCategory: category,
    note: null,
  };
}

/** Il nome con cui una riga si confronta con un nome nuovo: l'ingrediente a cui è
 * agganciata, o il testo con cui nascerà. */
function comparableName(line: FormLine): string {
  return (line.matchedName ?? line.label).trim().toLowerCase();
}

/** Aggiunge la riga di un nome nuovo, se non c'è già (R12). Due righe con lo stesso nome
 * diventerebbero lo stesso ingrediente al salvataggio, e il backend rifiuterebbe la
 * ricetta per la riga doppia: la riga che c'è si include e basta, come fa la scelta di
 * un ingrediente già in elenco. Una riga dell'AI che non sapeva il reparto («non in
 * anagrafica, sarà escluso») prende quello scelto, e così parte salvando. Torna anche la
 * chiave della riga, per darle il fuoco. */
export function addNewLine(
  lines: FormLine[],
  name: string,
  category: string
): { lines: FormLine[]; key: string } {
  const wanted = name.trim().toLowerCase();
  const existing = lines.find((line) => comparableName(line) === wanted);
  if (existing) {
    return {
      lines: lines.map((line) =>
        line.key === existing.key
          ? {
              ...line,
              included: true,
              proposedCategory:
                line.ingredientId === null ? line.proposedCategory ?? category : line.proposedCategory,
            }
          : line
      ),
      key: existing.key,
    };
  }
  const line = lineFromNewName(name, category);
  return { lines: [...lines, line], key: line.key };
}

export function lineFromRecipe(line: RecipeIngredientLine): FormLine {
  return {
    key: `recipe:${line.ingredient_id}`,
    label: line.ingredient_name,
    ingredientId: line.ingredient_id,
    matchedName: line.ingredient_name,
    uncertain: false,
    manual: true,
    role: line.role,
    // la dose scritta, mai quella riscalata: il modulo modifica la ricetta a 1×
    quantityText: line.quantity_text ?? "",
    included: true,
    proposedCategory: null,
    note: line.note,
  };
}

export function valuesFromRecipe(recipe: RecipeDetail): RecipeFormValues {
  return {
    title: recipe.title,
    description: recipe.description ?? "",
    category: recipe.category,
    servingsText: recipe.servings === null ? "" : String(recipe.servings),
    cost: recipe.cost,
    instructions: recipe.instructions,
    lines: recipe.ingredients.map(lineFromRecipe),
  };
}

/** Una bozza nuova sostituisce le proposte del modello, non il lavoro di chi scrive:
 * le righe scelte a mano restano, e la categoria anche (la bozza non ne propone). */
export function applyDraft(values: RecipeFormValues, draft: RecipeDraft): RecipeFormValues {
  return {
    ...values,
    title: draft.title,
    description: draft.description ?? "",
    instructions: draft.instructions,
    servingsText: String(draft.servings ?? ""),
    cost: draft.cost,
    lines: [...draft.ingredients.map(lineFromDraft), ...values.lines.filter((line) => line.manual)],
  };
}

/** Le righe che partono salvando: agganciate, o con nome e categoria per crearle. */
export function savableLines(lines: FormLine[]): FormLine[] {
  return lines.filter(
    (line) => line.included && (line.ingredientId !== null || line.proposedCategory !== null)
  );
}

export function matchNote(line: FormLine): string {
  if (line.ingredientId === null) {
    // il nome sta già sulla riga, sopra la nota: ripeterlo è quel che a 375px allargava
    // la pagina a 562px con un nome di 60 caratteri (e2e/ai-draft.spec.ts)
    if (line.proposedCategory !== null) return "da creare salvando";
    return `${line.label} non in anagrafica, sarà escluso`;
  }
  if (line.uncertain) return `${line.matchedName}, da confermare`;
  return line.matchedName ?? line.label;
}

/** Se la nota dell'aggancio dice qualcosa che l'etichetta non dice già. Una riga
 * scelta a mano o salvata porta lo stesso nome due volte (giro di T3): lì si tace. */
export function showsMatch(line: FormLine): boolean {
  if (line.ingredientId === null || line.uncertain) return true;
  return (line.matchedName ?? "").toLowerCase() !== line.label.toLowerCase();
}

/** Quello che il backend rifiuterebbe con un 422, detto qui in modo che si possa
 * correggere invece di riprovare a mandare gli stessi dati. `null` quando non c'è
 * niente da sistemare. */
export function validationProblem(values: RecipeFormValues): string | null {
  if (values.title.trim() === "" || values.instructions.trim() === "")
    return "Servono un titolo e un procedimento per salvare.";
  if (values.title.trim().length > TITLE_MAX)
    return `Il titolo è troppo lungo: massimo ${TITLE_MAX} caratteri.`;

  const servings = values.servingsText.trim();
  if (servings !== "" && !/^\d+$/.test(servings))
    return `Le porzioni vanno scritte come numero intero da ${SERVINGS_MIN} a ${SERVINGS_MAX}, oppure lasciate vuote.`;
  if (servings !== "" && (Number(servings) < SERVINGS_MIN || Number(servings) > SERVINGS_MAX))
    return `Le porzioni devono stare tra ${SERVINGS_MIN} e ${SERVINGS_MAX}. Lascia il campo vuoto se non lo sai: vuoto è meglio di inventato.`;

  const tooLong = savableLines(values.lines).find(
    (line) => line.quantityText.trim().length > QUANTITY_MAX
  );
  if (tooLong)
    return `La quantità di «${tooLong.label}» è troppo lunga: massimo ${QUANTITY_MAX} caratteri.`;

  return null;
}

function lineBody(line: FormLine): RecipeIngredientBody {
  // `quantity_text` è testo da mostrare, mai un numero da calcolare: passa verbatim, e
  // vuoto resta vuoto invece di diventare ""
  const quantity_text = line.quantityText.trim() === "" ? null : line.quantityText;
  // la nota solo se c'è: una chiave `note: null` in più cambierebbe il corpo che
  // «Scrivi una ricetta» ha sempre mandato
  const note = line.note ? { note: line.note } : {};
  return line.ingredientId !== null
    ? { ingredient_id: line.ingredientId, role: line.role, quantity_text, ...note }
    : {
        name: line.label.trim().toLowerCase(),
        category: line.proposedCategory,
        role: line.role,
        quantity_text,
        ...note,
      };
}

export function recipeBody(values: RecipeFormValues): RecipeBody {
  const servings = values.servingsText.trim();
  const description = values.description.trim();
  return {
    title: values.title.trim(),
    description: description === "" ? null : description,
    category: values.category,
    instructions: values.instructions,
    servings: servings === "" ? null : Number(servings),
    cost: values.cost,
    ingredients: savableLines(values.lines).map(lineBody),
  };
}

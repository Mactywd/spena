import type { Dispatch, SetStateAction } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ApiError } from "../../api/client";
import { IngredientPicker } from "../../components/IngredientPicker";
import { buttonClasses } from "../../components/ui/buttonClasses";
import { CostPicker } from "../../components/ui/CostPicker";
import { FOOD_CATEGORIES } from "../../domain/categories";
import type { Ingredient, IngredientRole, RecipeBody, RecipeDetail } from "../../domain/types";
import { CategoryField } from "./CategoryField";
import {
  QUANTITY_MAX,
  TITLE_MAX,
  lineFromIngredient,
  matchNote,
  recipeBody,
  savableLines,
  showsMatch,
  validationProblem,
  type FormLine,
  type RecipeFormValues,
} from "./formModel";

const ROLE_LABELS: Record<IngredientRole, string> = {
  primary: "principale",
  secondary: "secondario",
};

/** Cosa dire accanto al pulsante quando il salvataggio non va.
 *
 * Un rifiuto 4xx con una frase — il `detail` stringa che le rotte delle ricette scrivono
 * apposta: il non alimentare, la categoria sconosciuta, la riga doppia, l'ingrediente
 * sparito, la ricetta eliminata nel frattempo — si mostra com'è: dice già il passo dopo.
 * Un 422 di validazione di FastAPI porta invece un elenco di oggetti, che non è una
 * frase: lì resta il testo generico, e non dice «riprova», perché rimandare gli stessi
 * byte darà lo stesso esito. Un 5xx o una rete caduta non hanno niente di utile da dire:
 * «riprova», che lì è vero. */
function saveProblem(error: unknown): string {
  if (error instanceof ApiError && error.status >= 400 && error.status < 500) {
    const detail = (error.body as { detail?: unknown } | null)?.detail;
    if (typeof detail === "string") return detail;
    return "Il backend ha rifiutato la ricetta: qualcosa nei campi qui sopra non va. Correggilo — rimandarla identica darà lo stesso esito.";
  }
  return "Non sono riuscito a salvare la ricetta. Niente è andato perso: riprova.";
}

function LineRow({
  line,
  onUpdate,
  onRemove,
}: {
  line: FormLine;
  onUpdate: (change: Partial<FormLine>) => void;
  onRemove: () => void;
}) {
  // la stessa condizione di `savableLines`: una riga entra nel salvataggio se è
  // agganciata o se porta nome e categoria con cui crearla, ed è lì che ha dose e ruolo
  const savableShape = line.ingredientId !== null || line.proposedCategory !== null;
  return (
    <li className="flex flex-col gap-2 py-2 text-sm">
      {/* Prima riga: [la casella, solo se l'aggancio è incerto] + il nome + la ✕. Il nome
          prende lo spazio che resta e va a capo fra le parole; la ✕ non si stringe mai.
          La nota dell'aggancio sta sotto, su una riga sua: accanto al nome, in una riga
          `justify-between` che non si stringeva, allargava la pagina a 562px con un nome
          di 60 caratteri (e2e/ai-draft.spec.ts). */}
      <div className="flex items-center gap-2">
        <label className="flex min-h-11 min-w-0 flex-1 items-center gap-3">
          {/* La casella c'è solo dove l'AI ha un'ipotesi da confermare: lì vuol dire
              «è questo», non «tienila». Le righe si tolgono con la ✕ (R10 §6.2). */}
          {line.uncertain && (
            <input
              type="checkbox"
              aria-label={`Includi ${line.label}`}
              checked={line.included}
              onChange={() => onUpdate({ included: !line.included })}
              className="size-5 shrink-0"
            />
          )}
          <span className="min-w-0 flex-1 break-words">{line.label}</span>
        </label>
        {/* la stessa X delle pastiglie del filtro, e per la stessa ragione il nome
            accessibile nomina la riga: su dodici righe «Togli» da solo non dice quale */}
        <button
          type="button"
          aria-label={`Togli ${line.label}`}
          onClick={onRemove}
          className="flex size-11 shrink-0 items-center justify-center rounded-full text-ink-soft"
        >
          <svg
            viewBox="0 0 24 24"
            aria-hidden="true"
            className="size-4"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
          >
            <path d="M6 6l12 12M18 6L6 18" />
          </svg>
        </button>
      </div>

      {showsMatch(line) && (
        <p
          className={`text-xs ${
            line.ingredientId === null || line.uncertain ? "italic text-low" : "text-brand"
          }`}
        >
          {matchNote(line)}
        </p>
      )}

      {/* perché la casella parte vuota: senza questa frase "da confermare" sembra un
          avviso, non una cosa da fare */}
      {line.uncertain && (
        <p className="text-xs text-low">
          Parte escluso, perché l'aggancio è solo un'ipotesi: spunta la casella se è quello
          giusto.
        </p>
      )}

      {line.ingredientId === null && line.proposedCategory !== null && (
        <div className="flex flex-col gap-1">
          <p className="text-xs text-ink-soft">Non è in anagrafica: lo creo io salvando.</p>
          <label className="text-xs font-medium text-ink-soft">
            Categoria
            <select
              aria-label={`Categoria per «${line.label}»`}
              value={line.proposedCategory ?? "altro"}
              onChange={(e) => onUpdate({ proposedCategory: e.target.value })}
              className="mt-1"
            >
              {FOOD_CATEGORIES.map((category) => (
                <option key={category} value={category}>
                  {category}
                </option>
              ))}
            </select>
          </label>
        </div>
      )}

      {savableShape && (
        <div className="flex items-end gap-2">
          <label className="flex-1 text-xs text-ink-soft">
            Quantità
            <input
              aria-label={`Quantità per ${line.label}`}
              value={line.quantityText}
              onChange={(e) => onUpdate({ quantityText: e.target.value })}
              maxLength={QUANTITY_MAX}
              placeholder="q.b."
              className="mt-1.5 text-ink"
            />
          </label>
          {/* su ogni riga, anche su quelle proposte dall'AI: è il ruolo che decide se
              la ricetta è cucinabile (giro di T3) */}
          <div className="flex gap-1" role="group" aria-label={`Ruolo di ${line.label}`}>
            {(["primary", "secondary"] as IngredientRole[]).map((role) => (
              <button
                key={role}
                type="button"
                onClick={() => onUpdate({ role })}
                aria-pressed={line.role === role}
                // quello non scelto porta fondo e contorno suoi: un `bg-page` sul fondo
                // della pagina era un'etichetta, non un bottone da toccare
                className={`min-h-11 rounded-full px-3 py-2 text-xs font-medium ${
                  line.role === role
                    ? "bg-brand text-white"
                    : "bg-card text-ink-soft ring-1 ring-line ring-inset"
                }`}
              >
                {ROLE_LABELS[role]}
              </button>
            ))}
          </div>
        </div>
      )}
    </li>
  );
}

/** Il modulo di una ricetta, per scriverla e per modificarla (R10 §6.2).
 *
 * Controllato: i valori li tiene chi lo usa. «Scrivi una ricetta» ci versa dentro la
 * bozza dell'AI senza perdere le righe scelte a mano; la modifica lo riempie una volta
 * dalla ricetta salvata. Il salvataggio è la funzione che riceve — `POST` o `PUT` — e
 * il modulo ne mostra l'esito accanto al pulsante.
 */
export function RecipeForm({
  values,
  onChange,
  save,
  onSaved,
  submitLabel,
}: {
  values: RecipeFormValues;
  onChange: Dispatch<SetStateAction<RecipeFormValues>>;
  save: (body: RecipeBody) => Promise<RecipeDetail>;
  onSaved: (recipe: RecipeDetail) => void;
  submitLabel: string;
}) {
  const queryClient = useQueryClient();
  const savable = savableLines(values.lines);
  const problem = validationProblem(values);
  const submit = useMutation({
    mutationFn: () => save(recipeBody(values)),
    onSuccess: onSaved,
    onError: (error) => {
      // Un 422 può voler dire che la categoria scelta non c'è più (l'ultima ricetta che
      // la portava è stata eliminata nel frattempo): l'elenco si rilegge alla prossima
      // apertura, invece di riproporre la stessa voce sparita.
      if (error instanceof ApiError && error.status === 422)
        void queryClient.invalidateQueries({ queryKey: ["recipe-categories"] });
    },
  });

  function set(change: Partial<RecipeFormValues>) {
    onChange((prev) => ({ ...prev, ...change }));
  }

  function updateLine(key: string, change: Partial<FormLine>) {
    onChange((prev) => ({
      ...prev,
      lines: prev.lines.map((line) => (line.key === key ? { ...line, ...change } : line)),
    }));
  }

  function removeLine(key: string) {
    onChange((prev) => ({ ...prev, lines: prev.lines.filter((line) => line.key !== key) }));
  }

  function attach(ingredient: Ingredient) {
    onChange((prev) => {
      // due righe sullo stesso ingrediente sono un 409 del backend, e non vorrebbero
      // dire niente: se c'è già, la si include e basta — che è anche il modo di
      // confermare un aggancio incerto scegliendolo di persona
      if (prev.lines.some((line) => line.ingredientId === ingredient.id))
        return {
          ...prev,
          lines: prev.lines.map((line) =>
            line.ingredientId === ingredient.id ? { ...line, included: true } : line
          ),
        };
      return { ...prev, lines: [...prev.lines, lineFromIngredient(ingredient)] };
    });
  }

  return (
    <div className="flex flex-col gap-3">
      <label className="text-sm">
        Titolo
        <input
          value={values.title}
          onChange={(e) => set({ title: e.target.value })}
          maxLength={TITLE_MAX}
          className="mt-1.5"
        />
      </label>

      <label className="text-sm">
        Descrizione
        <textarea
          value={values.description}
          onChange={(e) => set({ description: e.target.value })}
          rows={2}
          placeholder="Facoltativa: una riga che la presenta"
          className="mt-1.5"
        />
      </label>

      <CategoryField value={values.category} onChange={(category) => set({ category })} />

      <label className="text-sm">
        Porzioni
        <input
          aria-label="Porzioni"
          value={values.servingsText}
          onChange={(e) => set({ servingsText: e.target.value })}
          inputMode="numeric"
          placeholder="Lascia vuoto se non lo sai"
          className="mt-1.5"
        />
      </label>

      <div className="text-sm">
        Costo
        <div className="flex items-center gap-2">
          <CostPicker value={values.cost} onChange={(cost) => set({ cost })} />
          {values.cost === null && <span className="text-ink-faint">non indicato</span>}
        </div>
      </div>

      <div>
        <h2 className="text-xs uppercase tracking-wide text-ink-faint">Ingredienti</h2>
        <ul className="divide-y divide-line">
          {values.lines.map((line) => (
            <LineRow
              key={line.key}
              line={line}
              onUpdate={(change) => updateLine(line.key, change)}
              onRemove={() => removeLine(line.key)}
            />
          ))}
        </ul>

        <IngredientPicker
          label="Aggiungi un ingrediente"
          failureNote="Puoi salvare la ricetta comunque, anche senza ingredienti agganciati."
          kind="food"
          onPick={attach}
        />
      </div>

      <label className="text-sm">
        Procedimento
        <textarea
          value={values.instructions}
          onChange={(e) => set({ instructions: e.target.value })}
          rows={8}
          className="mt-1.5"
        />
      </label>

      {/* una ricetta senza agganci si salva — è comunque la ricetta che l'utente
          voleva — ma va detto cosa ci rimette, prima del salvataggio e non dopo */}
      {savable.length === 0 && (
        <p role="status" className="text-sm text-low">
          Nessun ingrediente agganciato: la ricetta si salva comunque, ma il ricettario non
          potrà dire se puoi cucinarla.
        </p>
      )}

      {/* il motivo sta accanto al pulsante che sta disabilitando: un pulsante spento e
          muto è un vicolo cieco quanto un errore senza spiegazione */}
      {problem && <p className="text-sm text-low">{problem}</p>}

      <button
        type="button"
        onClick={() => submit.mutate()}
        disabled={submit.isPending || problem !== null}
        className={buttonClasses("primary", "block")}
      >
        {submit.isPending ? "Salvo…" : submitLabel}
      </button>

      {/* l'errore sta accanto al pulsante che ha fallito: tutti i campi restano qui,
          pronti per un altro tentativo */}
      {submit.isError && (
        <p role="alert" className="text-sm text-danger">
          {saveProblem(submit.error)}
        </p>
      )}
    </div>
  );
}

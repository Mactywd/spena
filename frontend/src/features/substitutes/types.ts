// I sostituti di R5, come li manda il backend (`backend/app/schemas/substitution.py`).
// Qui e non in `domain/types.ts`: li usano solo questa cartella e chi la monta.
import type { Availability } from "../../domain/types";

export type SubstitutionVerdict = "substitutes" | "omit" | "irreplaceable";
export type SubstitutionContext = "dolce" | "salato";
export type DecidedBy = "ai" | "human";

// Gli stessi limiti di `backend/app/domain/substitutions.py`: qui servono a non offrire il
// quarto selettore e a tagliare la nota, il server li controlla comunque. Un test del
// backend (`tests/test_frontend_substitutes.py`) li confronta.
export const SUBSTITUTES_MAX = 3;
export const SUBSTITUTE_NOTE_MAX = 60;

export interface Substitute {
  ingredient_id: string;
  /** Il nome canonico, minuscolo: la maiuscola solo a inizio riga, a video. */
  name: string;
  note: string | null;
}

export interface LineSubstitute extends Substitute {
  availability: Availability;
  /** In dispensa soddisfa la stessa regola della riga: «ce l'hai». Lo dice il server. */
  satisfied: boolean;
}

/** La risposta che vale per una riga di ricetta. */
export interface LineSubstitution {
  ingredient_id: string;
  ingredient_name: string;
  context: SubstitutionContext;
  /** La correzione di questa ricetta, o la voce generale; `null` senza risposta. */
  scope: "recipe" | "general" | null;
  verdict: SubstitutionVerdict | null;
  decided_by: DecidedBy | null;
  substitutes: LineSubstitute[];
  /** L'AI chiesta adesso non ha risposto, o ha risposto qualcosa che non si applica. */
  ai_failed: boolean;
}

export interface ContextSubstitution {
  context: SubstitutionContext;
  recipes: number;
  verdict: SubstitutionVerdict | null;
  decided_by: DecidedBy | null;
  substitutes: Substitute[];
}

export interface IngredientSubstitutions {
  ingredient_id: string;
  contexts: ContextSubstitution[];
  recipe_overrides: number;
}

export interface SubstitutionBody {
  verdict: SubstitutionVerdict;
  substitutes: { ingredient_id: string; note: string | null }[];
}

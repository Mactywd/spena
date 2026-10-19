import { useId, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { IngredientPicker } from "../../components/IngredientPicker";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { buttonClasses } from "../../components/ui/buttonClasses";
import { IconX } from "../../components/ui/icons";
import type { Ingredient } from "../../domain/types";
import { capitalizeFirst } from "../../lib/text";
import {
  SUBSTITUTE_NOTE_MAX,
  SUBSTITUTES_MAX,
  type Substitute,
  type SubstitutionBody,
  type SubstitutionVerdict,
} from "./types";
import { saveErrorText } from "./wording";

const CHOICES: { value: SubstitutionVerdict; label: string }[] = [
  { value: "substitutes", label: "Un altro ingrediente" },
  { value: "omit", label: "Si può omettere" },
  { value: "irreplaceable", label: "Insostituibile" },
];

type Chosen = { id: string; name: string; note: string };

/** Scrivere a mano una risposta di «Sostituisci» (R5): nella ricetta per quella ricetta
 * («Non va bene qui», «Scrivi tu»), in Anagrafica per un contesto. Chi lo monta dice dove
 * salvare (`save`) e cosa fare dopo (`onSaved`).
 *
 * I tre esiti sono pastiglie su radio veri, come i filtri del ricettario
 * (`MissingBudgetFilter`): la scelta singola e la tastiera sono del browser. Un sostituto
 * si sceglie solo dal cibo dell'anagrafica (decisione 2 di Mattia): niente «Aggiungi»
 * qui. Senza un `<form>`: l'Invio nel selettore non deve salvare a metà. */
export function SubstituteEditor<T>({
  legend,
  saveLabel,
  initialVerdict,
  initialSubstitutes,
  save,
  onSaved,
  onCancel,
}: {
  legend: string;
  saveLabel: string;
  initialVerdict: SubstitutionVerdict | null;
  initialSubstitutes: readonly Substitute[];
  save: (body: SubstitutionBody) => Promise<T>;
  onSaved: (result: T) => void;
  onCancel: () => void;
}) {
  const [verdict, setVerdict] = useState<SubstitutionVerdict>(initialVerdict ?? "substitutes");
  const [chosen, setChosen] = useState<Chosen[]>(
    initialSubstitutes.map((substitute) => ({
      id: substitute.ingredient_id,
      name: substitute.name,
      note: substitute.note ?? "",
    }))
  );
  const group = useId();
  const mutation = useMutation({
    mutationFn: (body: SubstitutionBody) => save(body),
    onSuccess: (result) => onSaved(result),
  });

  function pick(ingredient: Ingredient) {
    // lo stesso ingrediente scelto due volte non aggiunge una riga: c'è già
    setChosen((current) =>
      current.some((item) => item.id === ingredient.id)
        ? current
        : [...current, { id: ingredient.id, name: ingredient.name, note: "" }]
    );
  }

  function submit() {
    mutation.mutate({
      verdict,
      substitutes:
        verdict === "substitutes"
          ? chosen.map((item) => ({
              ingredient_id: item.id,
              // gli spazi li pulisce il server; vuota non è una nota
              note: item.note.trim() === "" ? null : item.note,
            }))
          : [],
    });
  }

  const reason = verdict === "substitutes" && chosen.length === 0 ? "Scegli almeno un ingrediente." : undefined;

  return (
    <div className="flex flex-col gap-3">
      <fieldset>
        <legend className="pb-1.5 text-sm font-medium text-ink-soft">{legend}</legend>
        <div className="flex flex-wrap gap-2">
          {CHOICES.map((choice) => {
            const checked = choice.value === verdict;
            return (
              <label key={choice.value}>
                <input
                  type="radio"
                  name={group}
                  className="peer sr-only"
                  checked={checked}
                  onChange={() => setVerdict(choice.value)}
                />
                <span
                  className={`${buttonClasses(checked ? "primary" : "secondary", "pill")} peer-focus-visible:ring-2 peer-focus-visible:ring-brand peer-focus-visible:ring-offset-2`}
                >
                  {choice.label}
                </span>
              </label>
            );
          })}
        </div>
      </fieldset>

      {verdict === "substitutes" && (
        <>
          {chosen.length > 0 && (
            <ul className="flex flex-col gap-2">
              {chosen.map((item) => (
                <li key={item.id} className="flex items-end gap-2">
                  <label className="min-w-0 flex-1 text-sm font-medium">
                    {capitalizeFirst(item.name)}
                    <input
                      aria-label={`Nota per ${item.name}`}
                      value={item.note}
                      maxLength={SUBSTITUTE_NOTE_MAX}
                      placeholder="Nota, per esempio: metà dose"
                      onChange={(event) => {
                        const note = event.target.value;
                        setChosen((current) =>
                          current.map((other) => (other.id === item.id ? { ...other, note } : other))
                        );
                      }}
                      className="mt-1.5"
                    />
                  </label>
                  <Button
                    variant="ghost"
                    icon={IconX}
                    label={`Togli ${item.name}`}
                    onClick={() => setChosen((current) => current.filter((other) => other.id !== item.id))}
                  />
                </li>
              ))}
            </ul>
          )}
          {chosen.length < SUBSTITUTES_MAX && (
            <IngredientPicker
              label={chosen.length === 0 ? "Cosa usare al suo posto" : "Aggiungine un altro"}
              kind="food"
              failureNote="Puoi scegliere «Si può omettere» o «Insostituibile»."
              emptyNote="Non è in anagrafica: un sostituto si sceglie fra gli ingredienti che ci sono."
              onPick={pick}
            />
          )}
        </>
      )}

      {mutation.isError && <Alert>{saveErrorText(mutation.error)}</Alert>}

      <div className="flex flex-col items-start gap-2">
        <Button variant="primary" busy={mutation.isPending} unavailableReason={reason} onClick={submit}>
          {saveLabel}
        </Button>
        <Button variant="ghost" onClick={onCancel}>
          Annulla
        </Button>
      </div>
    </div>
  );
}

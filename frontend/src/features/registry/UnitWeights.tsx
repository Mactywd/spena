import { useId, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { SectionHeading } from "../../components/ui/SectionHeading";
import { IconPencil } from "../../components/ui/icons";
import { formatNutrient } from "../../lib/nutrients";
import { registryRefusal } from "./api";
import { forgetWeight, nutritionKey, setWeight, type IngredientNutrition, type UnitWeight } from "./nutrition";

/** Il numero scritto nel campo: la virgola italiana, e più di zero. Il tetto dei 5000 g lo
 * dice il server, col suo perché (decisione 13 del piano). */
// eslint-disable-next-line react-refresh/only-export-components -- il contratto del piano le esporta
export function parseGrams(text: string): number | null {
  const trimmed = text.trim();
  if (trimmed === "") return null;
  const value = Number(trimmed.replace(",", "."));
  return Number.isFinite(value) && value > 0 ? value : null;
}

// eslint-disable-next-line react-refresh/only-export-components -- il contratto del piano le esporta
export function weightText(weight: UnitWeight): string {
  if (weight.state === "undecided") return "da decidere";
  const by = weight.decided_by === "human" ? "a mano" : "AI";
  if (weight.state === "none" || weight.grams === null) return `nessun peso · ${by}`;
  return `${formatNutrient(weight.grams, "g")} · ${by}`;
}

/** «Pesi per unità» (spec S4 §4.24): quanto pesa una unità di questo ingrediente, per
 * ogni dose delle sue ricette che non è in grammi o in litri. Un pannello alla volta. */
export function UnitWeights({ ingredientId, weights }: { ingredientId: string; weights: UnitWeight[] }) {
  const [editing, setEditing] = useState<string | null>(null);
  return (
    <section>
      <SectionHeading>Pesi per unità</SectionHeading>
      {weights.length === 0 ? (
        <p className="px-1 text-sm text-ink-soft">
          Nessuna dose da pesare: le sue ricette lo scrivono in grammi o in litri, oppure non lo usano.
        </p>
      ) : (
        <Card pad={false}>
          <ul className="px-3">
            {weights.map((weight) => (
              <WeightRow
                key={weight.unit}
                ingredientId={ingredientId}
                weight={weight}
                editing={editing === weight.unit}
                onEdit={() => setEditing(editing === weight.unit ? null : weight.unit)}
                onClose={() => setEditing(null)}
              />
            ))}
          </ul>
        </Card>
      )}
    </section>
  );
}

function WeightRow({
  ingredientId,
  weight,
  editing,
  onEdit,
  onClose,
}: {
  ingredientId: string;
  weight: UnitWeight;
  editing: boolean;
  onEdit: () => void;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const fieldId = useId();
  const label = `1 ${weight.unit_label}`;
  const currentText = weight.grams !== null ? String(weight.grams).replace(".", ",") : "";
  const [text, setText] = useState(currentText);
  const grams = parseGrams(text);

  async function done(next: IngredientNutrition) {
    queryClient.setQueryData(nutritionKey(ingredientId), next);
    // il conto di una ricetta aperta altrove cambia con un peso
    await queryClient.invalidateQueries({ queryKey: ["recipe-nutrition"] });
    onClose();
  }

  const save = useMutation({ mutationFn: (value: number) => setWeight(ingredientId, weight.unit, value), onSuccess: done });
  const forget = useMutation({ mutationFn: () => forgetWeight(ingredientId, weight.unit), onSuccess: done });
  const failure = save.error ?? forget.error;
  const refusal = registryRefusal(failure);

  // si riapre sul peso di adesso e senza l'avviso di un tentativo chiuso: né il numero di
  // prima di un «Annulla il peso», né il rifiuto di un «Lascia com'è»
  function open() {
    setText(currentText);
    save.reset();
    forget.reset();
    onEdit();
  }

  return (
    <li className="py-1">
      <div className="flex min-h-11 items-center gap-2">
        <span className="min-w-0 flex-1">{label}</span>
        <span className="shrink-0 text-sm text-ink-soft">{weightText(weight)}</span>
        <Button
          variant="ghost"
          icon={IconPencil}
          label={`Correggi il peso di ${label}`}
          aria-expanded={editing}
          onClick={open}
        />
      </div>
      {editing && (
        <div className="flex flex-col gap-2 pb-2">
          <label htmlFor={fieldId} className="text-sm font-medium">
            Grammi in {label}
          </label>
          <input
            id={fieldId}
            inputMode="decimal"
            autoComplete="off"
            value={text}
            onChange={(event) => setText(event.target.value)}
          />
          <div className="flex flex-col items-start gap-2">
            <Button
              variant="primary"
              busy={save.isPending}
              unavailableReason={grams === null ? "Scrivi un numero di grammi più grande di zero." : undefined}
              onClick={() => {
                if (grams !== null) save.mutate(grams);
              }}
            >
              Salva il peso
            </Button>
            {weight.state !== "undecided" && (
              <Button variant="secondary" busy={forget.isPending} onClick={() => forget.mutate()}>
                Annulla il peso
              </Button>
            )}
            <Button variant="ghost" onClick={onClose}>
              Lascia com'è
            </Button>
          </div>
          {failure && <Alert>{refusal?.detail ?? "Non sono riuscito a salvare il peso. Riprova."}</Alert>}
        </div>
      )}
    </li>
  );
}

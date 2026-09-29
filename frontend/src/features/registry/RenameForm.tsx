import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { buttonClasses } from "../../components/ui/buttonClasses";
import type { Ingredient, IngredientDetail } from "../../domain/types";
import { patchIngredient, refreshAfterCorrection, registryRefusal } from "./api";

/** «Rinomina» (spec §6.3). Un nome già preso non è un errore da riprovare: è un
 * doppione, e il rifiuto porta l'omonimo perché «Uniscili» apra la fusione con quel
 * vincitore già scelto (spec §7). Il nome scritto resta nel campo in ogni caso. */
export function RenameForm({
  ingredient,
  onDone,
  onMergeWith,
}: {
  ingredient: IngredientDetail;
  onDone: () => void;
  onMergeWith: (existing: Ingredient) => void;
}) {
  const queryClient = useQueryClient();
  const [name, setName] = useState(ingredient.display_name);
  const save = useMutation({
    mutationFn: (next: string) => patchIngredient(ingredient.id, { name: next }),
    onSuccess: async () => {
      await refreshAfterCorrection(queryClient);
      onDone();
    },
  });
  const refusal = registryRefusal(save.error);
  const existing = refusal?.code === "name_taken" ? (refusal.existing ?? null) : null;
  const cleaned = name.trim();
  // (F17) un pulsante spento e muto non si spiega da sé: il perché lo scrive Button sotto
  // di sé (`unavailableReason`, Consegna 6a). Il nome di ora è un «non ancora» anche lui:
  // basta scriverne un altro
  const notYet =
    cleaned === ""
      ? "Scrivi un nome per salvarlo."
      : cleaned === ingredient.display_name
        ? "È già il suo nome: scrivine un altro."
        : undefined;

  return (
    <Card as="section" className="mt-2 flex flex-col gap-3">
      <label className="text-sm font-medium text-ink-soft">
        Nuovo nome
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          disabled={save.isPending}
          className="mt-1.5"
        />
      </label>
      <p className="text-xs text-ink-faint">
        Il nome di prima resta come alias: chi lo scrive in lista ritrova questo ingrediente.
      </p>
      {/* in colonna: il perché che Button scrive sotto «Salva il nome» gli sta attaccato,
          e «Lascia com'è» non va a capo a metà riga */}
      <div className="flex flex-col items-start gap-2">
        <Button
          variant="primary"
          busy={save.isPending}
          unavailableReason={notYet}
          onClick={() => save.mutate(cleaned)}
        >
          Salva il nome
        </Button>
        <button type="button" onClick={onDone} className={buttonClasses("ghost")}>
          Lascia com'è
        </button>
      </div>
      {existing && (
        <div role="alert" className="flex flex-wrap items-center gap-2 text-sm">
          <span className="text-danger">C'è già «{existing.display_name}». Uniscili?</span>
          <button
            type="button"
            onClick={() => onMergeWith(existing)}
            className={buttonClasses("warn")}
          >
            Uniscili
          </button>
        </div>
      )}
      {refusal !== null && existing === null && <Alert>{refusal.detail}</Alert>}
      {save.isError && refusal === null && (
        <Alert>Non sono riuscito a rinominarlo. Il nome che hai scritto è ancora qui: riprova.</Alert>
      )}
    </Card>
  );
}

import { useId, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { IngredientFigure } from "../../components/IngredientFigure";
import { INGREDIENT_EMOJI } from "../../domain/emoji";
import type { IngredientDetail } from "../../domain/types";
import { patchIngredient, refreshAfterCorrection, registryRefusal } from "./api";

const CHOSEN = "bg-brand-tint ring-2 ring-brand ring-inset";

/** «Cambia figura» (S12, bozza §3.A): la figura delle righe di questo ingrediente in
 * Dispensa, scelta dall'elenco chiuso, o «Nessuna», che lascia l'icona del reparto.
 *
 * Una griglia di radio veri e non un `<select>`: una figura si sceglie guardandola, e un
 * menu nativo ne mostrerebbe una per riga, in piccolo, su 148 righe. Il radio nascosto dà
 * la selezione singola e le frecce della tastiera, come in `MissingBudgetFilter`; il nome
 * accessibile di ciascuno è l'emoji, che uno screen reader legge col suo nome («carota»).
 *
 * «Nessuna» si salva anche quando la scheda mostra già il ripiego: senza figura può voler
 * dire «non ancora decisa», e allora l'AI la deciderebbe al prossimo giro. Salvata a mano,
 * l'AI non la tocca più (`set_ingredient_emoji` nel servizio dell'anagrafica). */
export function EmojiForm({
  ingredient,
  onDone,
}: {
  ingredient: IngredientDetail;
  onDone: () => void;
}) {
  const queryClient = useQueryClient();
  const group = useId();
  const [choice, setChoice] = useState<string | null>(ingredient.emoji);
  const save = useMutation({
    mutationFn: (next: string | null) => patchIngredient(ingredient.id, { emoji: next }),
    onSuccess: async () => {
      // anche la dispensa: è lì che la figura si vede
      await refreshAfterCorrection(queryClient);
      onDone();
    },
  });
  const refusal = registryRefusal(save.error);
  const unchanged = choice !== null && choice === ingredient.emoji;

  return (
    <Card as="section" className="mt-2 flex flex-col gap-3">
      <fieldset>
        <legend className="pb-1.5 text-sm font-medium text-ink-soft">Figura in dispensa</legend>
        <label className="flex">
          <input
            type="radio"
            name={group}
            className="peer sr-only"
            checked={choice === null}
            onChange={() => setChoice(null)}
          />
          <span
            className={`flex min-h-11 flex-1 items-center gap-3 rounded-lg px-2 text-sm peer-focus-visible:ring-2 peer-focus-visible:ring-brand ${
              choice === null ? CHOSEN : ""
            }`}
          >
            <IngredientFigure emoji={null} category={ingredient.category} />
            Nessuna: l'icona del reparto
          </span>
        </label>
        <div className="grid grid-cols-[repeat(auto-fill,minmax(2.75rem,1fr))] justify-items-center gap-1 pt-2">
          {INGREDIENT_EMOJI.map((emoji) => (
            <label key={emoji}>
              <input
                type="radio"
                name={group}
                className="peer sr-only"
                checked={choice === emoji}
                onChange={() => setChoice(emoji)}
              />
              <span
                className={`flex size-11 items-center justify-center rounded-lg text-2xl leading-none peer-focus-visible:ring-2 peer-focus-visible:ring-brand ${
                  choice === emoji ? CHOSEN : "bg-page"
                }`}
              >
                {emoji}
              </span>
            </label>
          ))}
        </div>
      </fieldset>
      {/* in colonna, come «Cambia reparto»: il perché sta attaccato a «Salva la figura» */}
      <div className="flex flex-col items-start gap-2">
        <Button
          variant="primary"
          busy={save.isPending}
          unavailableReason={unchanged ? "È già la sua figura: scegline un'altra." : undefined}
          onClick={() => save.mutate(choice)}
        >
          Salva la figura
        </Button>
        <Button variant="ghost" onClick={onDone}>
          Lascia com'è
        </Button>
      </div>
      {refusal !== null && <Alert>{refusal.detail}</Alert>}
      {save.isError && refusal === null && (
        <Alert>Non sono riuscito a cambiare la figura. Riprova.</Alert>
      )}
    </Card>
  );
}

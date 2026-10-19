import { useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { NutrientTable } from "../../components/NutrientTable";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { SectionHeading } from "../../components/ui/SectionHeading";
import { CiqualPicker } from "./CiqualPicker";
import { decidedText, fetchNutrition, forgetFood, nutritionKey, type IngredientNutrition } from "./nutrition";

/** «Valori nutrizionali» nella scheda di un alimento in Anagrafica (S4, fetta 1).
 *
 * Legge la sua rotta, non la scheda: così la scheda non cambia forma (spec §4.17). Una
 * lettura fallita non è un avviso (`role="alert"`) e il suo pulsante non si chiama
 * «Riprova»: la scheda ha già i suoi, e due con lo stesso nome non si distinguerebbero. */
export function NutritionSection({ ingredientId }: { ingredientId: string }) {
  const queryClient = useQueryClient();
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: nutritionKey(ingredientId),
    queryFn: () => fetchNutrition(ingredientId),
  });
  const [picking, setPicking] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const forget = useMutation({
    mutationFn: () => forgetFood(ingredientId),
    onSuccess: (next) => {
      queryClient.setQueryData(nutritionKey(ingredientId), next);
      setNote("Scelta annullata: l'AI lo abbinerà al prossimo giro.");
    },
  });

  function pick() {
    setNote(null);
    forget.reset();
    setPicking(true);
  }

  let body: ReactNode;
  if (isLoading) {
    body = <p className="text-sm text-ink-soft">Carico i valori nutrizionali…</p>;
  } else if (isError || !data) {
    body = (
      <div className="flex flex-col items-start gap-2">
        <p className="text-sm text-ink-soft">Non sono riuscito a leggere i valori nutrizionali.</p>
        <Button variant="secondary" onClick={() => void refetch()}>
          Riprova a leggerli
        </Button>
      </div>
    );
  } else if (picking) {
    body = (
      <CiqualPicker
        ingredientId={ingredientId}
        current={data.food?.code ?? null}
        onDone={() => setPicking(false)}
      />
    );
  } else {
    body = (
      <Decision
        data={data}
        note={note}
        onPick={pick}
        onForget={() => forget.mutate()}
        forgetting={forget.isPending}
        forgetFailed={forget.isError}
      />
    );
  }

  return (
    <section>
      <SectionHeading>Valori nutrizionali</SectionHeading>
      <Card className="flex flex-col gap-3">
        {body}
        {/* la citazione che la licenza di CIQUAL chiede accanto a ogni riuso */}
        <p className="text-xs text-ink-faint">
          Fonte: Anses, Table de composition nutritionnelle des aliments Ciqual 2025.
        </p>
      </Card>
    </section>
  );
}

function Decision({
  data,
  note,
  onPick,
  onForget,
  forgetting,
  forgetFailed,
}: {
  data: IngredientNutrition;
  note: string | null;
  onPick: () => void;
  onForget: () => void;
  forgetting: boolean;
  forgetFailed: boolean;
}) {
  if (data.state === "undecided") {
    return (
      <div className="flex flex-col items-start gap-2">
        {note && (
          <p role="status" className="text-sm font-medium text-brand">
            {note}
          </p>
        )}
        <p className="text-sm">
          Non ancora abbinato a un alimento della tabella CIQUAL: lo farà l'AI al prossimo giro, oppure
          sceglilo tu.
        </p>
        <Button variant="secondary" onClick={onPick}>
          Scegli l'alimento
        </Button>
      </div>
    );
  }
  // una risposta che non è nessuno dei due stati qui sotto (`non_food`, o un corpo
  // inatteso) non disegna niente: la scheda non mostra la sezione a una voce non alimentare
  if (data.state !== "food" && data.state !== "none") return null;
  const food = data.state === "food" ? data.food : null;
  return (
    <>
      <div>
        <p className="font-medium">{food ? food.name_fr : "Nessun alimento adatto"}</p>
        <p className="text-xs text-ink-soft">
          {food
            ? `${data.source} · ${food.code} · ${decidedText(data.decided_by)}`
            : `${data.source} · ${decidedText(data.decided_by)}`}
        </p>
      </div>
      {food && <NutrientTable caption="Per 100 g" rows={data.nutrients ?? []} />}
      <div className="flex flex-col items-start gap-2">
        <Button variant="secondary" onClick={onPick}>
          Cambia alimento
        </Button>
        <Button variant="ghost" busy={forgetting} onClick={onForget}>
          Annulla la scelta
        </Button>
      </div>
      {forgetFailed && <Alert>Non sono riuscito ad annullare la scelta. Riprova.</Alert>}
    </>
  );
}

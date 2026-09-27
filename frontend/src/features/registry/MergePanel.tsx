import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { IngredientPicker } from "../../components/IngredientPicker";
import { Alert } from "../../components/ui/Alert";
import { Card } from "../../components/ui/Card";
import { buttonClasses } from "../../components/ui/buttonClasses";
import type { Ingredient, IngredientDetail } from "../../domain/types";
import { defaultQueryRetryPredicate } from "../../lib/queryRetry";
import { mergeIngredient, refreshAfterCorrection, registryRefusal } from "./api";
import { ingredientPath, type Origin } from "./origin";
import { mergePreviewText, mergeSlowWarning } from "./wording";

/** «Unisci a un altro…» (spec §6.3): la scelta del vincitore, l'anteprima, «Unisci».
 *
 * L'anteprima è una query e non una mutazione: è il dato di una coppia (perdente,
 * vincitore), e il server la calcola eseguendo la fusione vera dentro un SAVEPOINT che
 * annulla (§5.1). `staleTime: Infinity` e niente `refetchOnWindowFocus` (deciso al
 * Task 11, F13): sopra i 1.000 ricette una fusione può prendere minuti, e non si
 * ririfà da capo per un cambio di finestra o perché un'altra correzione ha invalidato
 * `["registry"]` — riparte solo quando cambia il vincitore scelto, che è nella query
 * key. Un rifiuto non si ritenta: è una risposta, non un guasto. */
export function MergePanel({
  ingredient,
  initialWinner,
  origin,
  onClose,
  onChangeCategory,
}: {
  ingredient: IngredientDetail;
  /** già scelto quando si arriva da «Uniscili» della rinomina */
  initialWinner: Ingredient | null;
  origin: Origin;
  onClose: () => void;
  /** l'uscita del rifiuto `kind_mismatch`: il cambio di reparto (spec §7) */
  onChangeCategory: () => void;
}) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [winner, setWinner] = useState<Ingredient | null>(initialWinner);

  const preview = useQuery({
    queryKey: ["registry", "merge-preview", ingredient.id, winner?.id ?? null],
    queryFn: () =>
      winner
        ? mergeIngredient(ingredient.id, winner.id, true)
        : Promise.reject(new Error("nessun ingrediente scelto")),
    enabled: winner !== null,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    retry: (count, error) => registryRefusal(error) === null && defaultQueryRetryPredicate(count, error),
  });

  const merge = useMutation({
    mutationFn: (into: string) => mergeIngredient(ingredient.id, into, false),
    onSuccess: (counts) => {
      // Prima si segna tutto come vecchio senza rileggere, poi si va: rileggere subito
      // chiederebbe al server la scheda del perdente, che non esiste più. La scheda del
      // vincitore, montata dopo, rilegge da sé.
      void refreshAfterCorrection(queryClient, false);
      navigate(ingredientPath(counts.winner_id, origin), { state: { merged: counts } });
    },
  });

  const counts = preview.data;
  const refusal = registryRefusal(preview.error) ?? registryRefusal(merge.error);
  // il perdente è questo ingrediente, non il vincitore: è lui che sparisce dentro la
  // fusione, e il suo numero di ricette è quello che decide quanto ci vuole (Task 11)
  const slowWarning = winner !== null ? mergeSlowWarning(ingredient.usage.recipes) : null;
  const busy = preview.isFetching || merge.isPending;

  return (
    <Card as="section" className="mt-2 flex flex-col gap-3">
      <h2 className="font-medium">Unisci «{ingredient.display_name}» a un altro ingrediente</h2>

      {winner === null ? (
        <IngredientPicker
          label="Unisci a"
          failureNote="Il doppione resta com'è: riprova tra poco."
          onPick={setWinner}
        />
      ) : (
        <p className="flex flex-wrap items-center gap-2 text-sm">
          <span>
            Resta: <span className="font-medium">«{winner.display_name}»</span>
          </span>
          <button
            type="button"
            disabled={busy}
            onClick={() => setWinner(null)}
            className={buttonClasses("ghost")}
          >
            Cambia
          </button>
        </p>
      )}

      {slowWarning && <p className="text-sm text-low">{slowWarning}</p>}

      {winner !== null && preview.isPending && (
        <p className="text-sm text-ink-soft">Calcolo cosa si sposta…</p>
      )}

      {counts && (
        <>
          <p className="text-sm">{mergePreviewText(counts)}</p>
          <button
            type="button"
            disabled={merge.isPending}
            onClick={() => merge.mutate(counts.winner_id)}
            className={buttonClasses("warn", "block")}
          >
            {merge.isPending ? "Unisco…" : "Unisci"}
          </button>
        </>
      )}

      {refusal?.code === "kind_mismatch" && (
        <div role="alert" className="flex flex-col gap-2 text-sm">
          <p className="text-danger">{refusal.detail}</p>
          <button type="button" onClick={onChangeCategory} className={buttonClasses("secondary")}>
            Cambia reparto
          </button>
        </div>
      )}
      {refusal !== null && refusal.code !== "kind_mismatch" && <Alert>{refusal.detail}</Alert>}
      {refusal === null && preview.isError && (
        <div role="alert" className="flex flex-wrap items-center gap-2 text-sm">
          <span className="text-danger">Non sono riuscito a calcolare l'anteprima.</span>
          <button type="button" onClick={() => void preview.refetch()} className={buttonClasses("secondary")}>
            Riprova
          </button>
        </div>
      )}
      {refusal === null && merge.isError && (
        <div role="alert" className="flex flex-wrap items-center gap-2 text-sm">
          <span className="text-danger">Non sono riuscito a unirli. Niente è cambiato.</span>
          <button
            type="button"
            // il bottone «Unisci» che ha appena fallito esiste solo quando `counts`
            // c'è: la stessa anteprima, ancora in cache (`staleTime: Infinity`),
            // dice ancora chi è il vincitore
            onClick={() => merge.mutate(counts!.winner_id)}
            className={buttonClasses("secondary")}
          >
            Riprova
          </button>
        </div>
      )}

      <button type="button" onClick={onClose} className={buttonClasses("ghost")}>
        Lascia com'è
      </button>
    </Card>
  );
}

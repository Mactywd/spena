import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { ApiError } from "../../api/client";
import { IngredientPicker } from "../../components/IngredientPicker";
import { Alert } from "../../components/ui/Alert";
import { Card } from "../../components/ui/Card";
import { buttonClasses } from "../../components/ui/buttonClasses";
import type { Ingredient, IngredientDetail } from "../../domain/types";
import { mergeIngredient, refreshAfterCorrection, registryRefusal } from "./api";
import { ingredientPath, type Origin } from "./origin";
import { mergePreviewText, mergeSlowWarning } from "./wording";

/** «Unisci a un altro…» (spec §6.3): la scelta del vincitore, l'anteprima, «Unisci».
 *
 * L'anteprima è una query e non una mutazione: è il dato di una coppia (perdente,
 * vincitore), e il server la calcola eseguendo la fusione vera dentro un SAVEPOINT che
 * annulla (§5.1). `staleTime: Infinity` e niente `refetchOnWindowFocus` (deciso al
 * Task 11, F13): senza uno stale time infinito il montaggio o un cambio di finestra la
 * rilancerebbero da soli, e ogni lancio è una fusione intera. Un'invalidazione esplicita
 * la rilancia comunque — `staleTime` non blocca quella — ed è voluto: se uno spostamento
 * d'alias cambia i conti mentre il pannello è aperto, l'anteprima deve dirlo, ed è
 * proprio `["registry"]` che `refreshAfterCorrection` invalida. Riparte anche quando
 * cambia il vincitore scelto, che è nella query key. Un rifiuto non si ritenta: è una
 * risposta, non un guasto — e nemmeno un guasto si ritenta da solo (`retry: 0` sotto):
 * ogni tentativo è una fusione intera dentro un SAVEPOINT, fino a 130s e 300s a nginx,
 * e il predicato di retry vero ne metterebbe in coda fino a tre prima di mostrare
 * «Riprova» — quasi un quarto d'ora. Qui il recupero è il bottone, non il predicato. */
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
    retry: 0,
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
    onError: () => {
      // Una richiesta caduta a metà (rete, un 504) non dice se la fusione — che il
      // server esegue per intero prima di rispondere — sia arrivata in fondo: solo
      // rileggere il perdente lo sa. Un 404 qui è già la risposta (il perdente non
      // c'è già più), ma la strada è la stessa: si rilegge con `refetch` acceso, e se
      // il perdente non c'è più è la sua stessa scheda a scoprirlo e a passare alla
      // schermata «non c'è più» (§6.3) — invece di un «Riprova» che ripeterebbe lo
      // stesso 404 in eterno. L'anteprima resta fuori (`excludeQueryKey`): non è lei
      // ad essere fallita, e rilanciarla vorrebbe dire un'altra fusione intera (~130s)
      // in silenzio dietro un errore che non la riguarda (fix round 2).
      void refreshAfterCorrection(queryClient, true, ["registry", "merge-preview"]);
    },
  });

  const counts = preview.data;
  const refusal = registryRefusal(preview.error) ?? registryRefusal(merge.error);
  // un 404 sulla POST della fusione vera vuol dire che il perdente non c'è già più:
  // è già successo, non un guasto da ritentare (Important 2)
  const mergeAlreadyDone = merge.error instanceof ApiError && merge.error.status === 404;
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
            onClick={() => {
              // altrimenti l'alert della fusione fallita resta in vista col vincitore
              // sbagliato sotto, e il suo «Riprova» punterebbe a un'anteprima che non
              // c'è più (Minor a)
              merge.reset();
              setWinner(null);
            }}
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
          <span className="text-danger">
            {mergeAlreadyDone
              ? `«${ingredient.display_name}» risulta già unito: aggiorno la scheda.`
              : "Non so se l'unione sia riuscita: sto controllando."}
          </span>
          {/* niente «Riprova» per un 404: il perdente non c'è già più, e ritentare
              vorrebbe dire lo stesso 404 all'infinito (Important 2). Compare solo se
              `counts` c'è ancora, la stessa anteprima in cache che dice il vincitore */}
          {!mergeAlreadyDone && counts && (
            <button
              type="button"
              onClick={() => merge.mutate(counts.winner_id)}
              className={buttonClasses("secondary")}
            >
              Riprova
            </button>
          )}
        </div>
      )}

      <button type="button" disabled={merge.isPending} onClick={onClose} className={buttonClasses("ghost")}>
        Lascia com'è
      </button>
    </Card>
  );
}

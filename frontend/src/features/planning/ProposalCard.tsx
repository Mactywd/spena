import { useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ApiError } from "../../api/client";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { useNotice } from "../../components/ui/noticeContext";
import type { Meal, MealProposal, PlanningChat, ProposalRow } from "../../domain/types";
import { MEALS_KEY } from "../meals/api";
import { SLOT_LABELS, longDayLabel } from "../meals/format";
import { PLANNING_KEY, placeProposal, putPlanningChat } from "./api";

/** Il corpo di un 409 di «Metti nella settimana». */
type PlaceRefusal = {
  code?: string;
  detail?: string;
  chat?: PlanningChat | null;
  occupants?: Meal[];
};

/** Che cosa fa la riga al suo posto: lo decide il backend (`effect`), qui si dice. */
function effectText(row: ProposalRow): string | null {
  if (row.occupant === null) return null;
  if (row.effect === "replace") return `Al posto di «${row.occupant.dish}»`;
  if (row.effect === "officialize") return `La bozza «${row.occupant.dish}» diventa ufficiale`;
  return null;
}

/** La proposta di Claude, posto per posto (spec §5.2), con «Metti nella settimana». I posti
 * occupati si sostituiscono solo dopo la conferma; il messaggio che segue la messa lo
 * scrive il backend e lo manda la schermata (`onPlaced`). */
export function ProposalCard({
  proposal,
  onPlaced,
}: {
  proposal: MealProposal;
  onPlaced: (followUp: string) => void;
}) {
  const queryClient = useQueryClient();
  const notice = useNotice();
  // una richiesta sola anche con due tocchi ravvicinati: lo stato di React arriva tardi
  const inFlight = useRef(false);
  const [busy, setBusy] = useState(false);
  const [occupants, setOccupants] = useState<Meal[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  // una mutazione: un 401 riporta all'accesso come ogni altra scrittura
  const placing = useMutation({
    mutationFn: (replace: boolean) => placeProposal(proposal.id, replace),
  });

  async function place(replace: boolean) {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setError(null);
    try {
      const result = await placing.mutateAsync(replace);
      setOccupants(null);
      putPlanningChat(queryClient, result.chat);
      notice({ text: "Pasti messi nella settimana." });
      void queryClient.invalidateQueries({ queryKey: MEALS_KEY });
      void queryClient.invalidateQueries({ queryKey: PLANNING_KEY });
      onPlaced(result.follow_up);
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        const body = e.body as PlaceRefusal | null;
        if (body?.chat) putPlanningChat(queryClient, body.chat);
        if (body?.code === "slots_taken") {
          setOccupants(body.occupants ?? []);
        } else if (body?.code === "proposal_placed") {
          // già messa (un altro tocco, un'altra scheda aperta): la chat in cache lo mostra
          setOccupants(null);
        } else {
          setOccupants(null);
          setError(body?.detail ?? "Non si può fare.");
        }
      } else {
        setError("Non è andata a buon fine. Riprova.");
      }
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }

  return (
    <Card as="section" className="flex flex-col gap-3">
      <h3 className="text-base font-semibold">
        {proposal.kind === "draft" ? "Bozza per la spesa" : "Proposta"}
      </h3>
      <ul className="flex flex-col">
        {proposal.rows.map((row) => {
          const effect = effectText(row);
          return (
            <li key={`${row.day}-${row.slot}`} className="border-t border-line py-2 first:border-t-0 first:pt-0">
              <p className="text-xs text-ink-soft">{`${longDayLabel(row.day)} · ${SLOT_LABELS[row.slot]}`}</p>
              <p className="font-medium break-words">{row.dish}</p>
              {row.sides && <p className="text-sm break-words text-ink-soft">{row.sides}</p>}
              {effect && <p className="text-sm break-words">{effect}</p>}
            </li>
          );
        })}
      </ul>

      {proposal.status === "placed" && <p className="text-sm font-medium">Messa nella settimana.</p>}
      {proposal.status === "superseded" && (
        <p className="text-sm text-ink-soft">Sostituita da una proposta più nuova.</p>
      )}

      {proposal.status === "open" &&
        (occupants === null ? (
          <Button variant="primary" shape="block" busy={busy} onClick={() => void place(false)}>
            Metti nella settimana
          </Button>
        ) : (
          <div className="flex flex-col gap-2">
            <p className="text-sm font-medium">Questi posti sono occupati:</p>
            <ul className="flex flex-col gap-1">
              {occupants.map((m) => (
                <li key={m.id} className="text-sm break-words">
                  {`${longDayLabel(m.day)} · ${SLOT_LABELS[m.slot]}: «${m.dish}»`}
                </li>
              ))}
            </ul>
            <Button variant="primary" shape="block" busy={busy} onClick={() => void place(true)}>
              Sostituisci e metti
            </Button>
            <Button variant="ghost" shape="block" busy={busy} onClick={() => setOccupants(null)}>
              Annulla
            </Button>
          </div>
        ))}
      {error && <Alert>{error}</Alert>}
    </Card>
  );
}

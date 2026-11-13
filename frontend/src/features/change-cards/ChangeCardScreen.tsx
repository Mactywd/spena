import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { ApiError } from "../../api/client";
import { BackLink } from "../../components/BackLink";
import { ErrorState } from "../../components/ui/ErrorState";
import { cardKey, fetchCard } from "./api";
import { ChangeCard } from "./ChangeCard";

/** La scheda dei cambi a tutta pagina (`/pasti/cambi/:id`). */
export function ChangeCardScreen() {
  const { id = "" } = useParams();
  const card = useQuery({ queryKey: cardKey(id), queryFn: () => fetchCard(id) });
  return (
    <div className="flex flex-col gap-3 px-4 pt-2 pb-6">
      <BackLink to="/pasti" label="Pasti" />
      <h1 className="text-xl font-semibold">Scheda dei cambi</h1>
      {card.isError ? (
        card.error instanceof ApiError && card.error.status === 404 ? (
          <p className="text-sm text-ink-soft">Questa scheda non c'è più.</p>
        ) : (
          <ErrorState
            message="La scheda non si carica."
            onRetry={() => card.refetch()}
            retrying={card.isFetching}
          />
        )
      ) : card.data ? (
        <ChangeCard card={card.data} />
      ) : (
        <p className="text-sm text-ink-soft">Carico la scheda…</p>
      )}
    </div>
  );
}

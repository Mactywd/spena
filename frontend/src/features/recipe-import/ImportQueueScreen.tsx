import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert } from "../../components/ui/Alert";
import { Screen } from "../../components/ui/Screen";
import { decideTerm, fetchImportStatus, fetchImportTerms, fetchTermProposals } from "./api";
import { TermCard, type Decision } from "./TermCard";
import { useState } from "react";

/** La revisione dei termini dell'import.
 *
 * Una decisione per volta, e ogni decisione materializza subito le ricette che
 * aspettavano quel termine: il numero che torna è ciò che rende questa schermata un
 * lavoro con un risultato visibile invece di un modulo da compilare.
 */
export function ImportQueueScreen() {
  const queryClient = useQueryClient();
  const [lastUnlocked, setLastUnlocked] = useState<number | null>(null);

  const { data: terms = [], isLoading, isError } = useQuery({
    queryKey: ["import-terms"],
    queryFn: fetchImportTerms,
  });

  const { data: status } = useQuery({
    queryKey: ["import-status"],
    queryFn: fetchImportStatus,
  });

  // Le proposte arrivano in una query loro: se Claude non risponde la coda resta
  // usabile, e il guasto non può svuotare una schermata che funziona anche senza.
  const termIds = terms.map((term) => term.id);
  const proposalsEnabled = termIds.length > 0;
  const { data: proposals, isError: proposalsFailed } = useQuery({
    queryKey: ["import-proposals", termIds.join(",")],
    queryFn: () => fetchTermProposals(termIds),
    enabled: proposalsEnabled,
    staleTime: Infinity,
  });

  // La coda mostra un termine solo quando si sa già se le proposte ci sono: senza
  // questo, «Rigatoni» apparirebbe un istante prima di «decidi a mano», e chi guarda
  // vedrebbe un pulsante sparire o un avviso comparire da solo un attimo dopo.
  const proposalsSettled = !proposalsEnabled || proposals !== undefined || proposalsFailed;
  const loading = isLoading || !proposalsSettled;

  const decide = useMutation({
    mutationFn: ({ termId, decision }: { termId: string; decision: Decision }) =>
      decideTerm(termId, decision),
    onSuccess: (result) => {
      setLastUnlocked(result.unlocked);
      // la coda e lo stato cambiano entrambi, e il ricettario è appena cresciuto:
      // senza questa riga l'utente torna a Ricette e non vede quel che ha sbloccato
      queryClient.invalidateQueries({ queryKey: ["import-terms"] });
      queryClient.invalidateQueries({ queryKey: ["import-status"] });
      queryClient.invalidateQueries({ queryKey: ["recipes"] });
    },
  });

  const byTerm = new Map((proposals?.proposals ?? []).map((p) => [p.term_id, p]));

  return (
    <Screen title="Ingredienti da abbinare">
      <p className="text-sm text-ink-soft">
        Ogni nome deciso vale per sempre, e le ricette che lo aspettavano entrano nel
        ricettario da sé.
      </p>

      {status && status.pending_recipes > 0 && (
        <p className="pt-1 text-xs text-ink-faint">
          {status.pending_recipes} ricette scaricate aspettano, {status.imported} sono già dentro.
        </p>
      )}

      {lastUnlocked !== null && (
        <p className="pt-2 text-sm font-medium text-brand">
          {lastUnlocked === 0
            ? "Decisione registrata: nessuna ricetta era in attesa solo di questa."
            : `Sbloccate ${lastUnlocked} ricette.`}
        </p>
      )}

      {/* una constatazione, non un guasto: la coda funziona anche senza proposte */}
      {proposalsFailed && (
        <p className="pt-2 text-xs text-ink-faint">
          Le proposte non sono disponibili: decidi a mano, il suggerimento qui sotto
          viene dalla somiglianza dei nomi.
        </p>
      )}

      {decide.isError && (
        <Alert className="pt-2">
          Non sono riuscito a registrare la decisione. Niente è andato perso: riprova.
        </Alert>
      )}

      {loading && <p className="pt-4 text-ink-soft">Carico la coda…</p>}

      {!loading && isError && (
        <Alert className="pt-4">
          Non sono riuscito a leggere la coda. Il ricettario funziona comunque: le
          ricette già importate sono al loro posto.
        </Alert>
      )}

      {!loading && !isError && terms.length === 0 && (
        <p className="pt-4 text-ink-soft">
          Niente da abbinare. Ogni ingrediente delle ricette scaricate ha la sua
          decisione.
        </p>
      )}

      {!loading && terms.length > 0 && (
        <ul className="flex flex-col gap-2 pt-2">
          {terms.map((term) => (
            <TermCard
              key={term.id}
              term={term}
              proposal={byTerm.get(term.id) ?? null}
              suggestionName={term.suggestion?.name ?? null}
              pending={decide.isPending}
              onDecide={(decision) => decide.mutate({ termId: term.id, decision })}
            />
          ))}
        </ul>
      )}
    </Screen>
  );
}

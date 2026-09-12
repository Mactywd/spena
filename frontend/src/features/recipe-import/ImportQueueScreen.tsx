import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError } from "../../api/client";
import { Alert } from "../../components/ui/Alert";
import { Screen } from "../../components/ui/Screen";
import { decideTerm, fetchImportStatus, fetchImportTerms, fetchTermProposals } from "./api";
import { TermCard, type Decision } from "./TermCard";
import type { TermProposal } from "../../domain/types";

/** Il messaggio da mostrare quando una decisione fallisce.
 *
 * Un 4xx porta nel suo `detail` (già in `ApiError.message` grazie ad
 * `apiFetch`) il motivo vero — per esempio un 409 che dice "collega il termine
 * invece di creare un duplicato" quando l'utente rinomina "Sale fino" nel
 * generico "sale". Mostrarlo è l'unica cosa che gli dice dov'è l'uscita: la
 * frase generica ("riprova") lo rimanda a riprovare la stessa azione che ha
 * già fallito. Un 5xx o una rete caduta non hanno un `detail` utile, quindi
 * restano sulla frase generica — che lì è vera.
 */
function decisionErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.status >= 400 && error.status < 500) {
    return error.message;
  }
  return "Non sono riuscito a registrare la decisione. Niente è andato perso: riprova.";
}

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

  // Le proposte di Claude, conservate per termine una volta arrivate. Il backend
  // filtra `/imports/terms` ai soli termini ancora in attesa: dopo una decisione
  // l'elenco si accorcia da sé, e senza questa cache quell'accorciarsi cambierebbe
  // la domanda fatta a Claude a ogni tocco — una richiesta intera per il lotto
  // residuo invece di zero, perché il lotto residuo ha già la sua risposta.
  //
  // L'aggiornamento vive dentro `queryFn`, non in un `useEffect`: è la risposta
  // della richiesta stessa, non una reazione a un cambiamento già avvenuto, quindi
  // non c'è un secondo giro di render da incatenare a quello che React Query fa
  // già da sé quando la query si risolve.
  const [proposalsByTerm, setProposalsByTerm] = useState<Map<string, TermProposal>>(
    () => new Map()
  );

  const termIds = terms.map((term) => term.id);
  // solo i termini che non hanno ancora una proposta nota: con tutti già noti non
  // c'è niente da chiedere, e la query resta disabilitata — zero chiamate, non una.
  const missingTermIds = termIds.filter((id) => !proposalsByTerm.has(id));

  const proposalsQuery = useQuery({
    queryKey: ["import-proposals", missingTermIds.join(",")],
    queryFn: async () => {
      const result = await fetchTermProposals(missingTermIds);
      setProposalsByTerm((prev) => {
        const next = new Map(prev);
        for (const proposal of result.proposals) {
          next.set(proposal.term_id, proposal);
        }
        return next;
      });
      return result;
    },
    enabled: missingTermIds.length > 0,
    staleTime: Infinity,
    // Il 503 di questa rotta quando manca ANTHROPIC_API_KEY è un degrado dichiarato
    // e permanente per tutta la vita del processo, non un intoppo passeggero: il
    // default dell'app (vedi il commento in App.tsx) lo ritenterebbe due volte
    // prima di mostrare "decidi a mano", per tre giri di rete che non cambieranno
    // mai esito. Solo questa query lo spegne: il default resta quello che è per
    // tutte le altre schermate.
    retry: false,
  });

  // Cosa dipende dalla risposta di Claude — la scorciatoia in scheda e l'avviso
  // «decidi a mano» — aspetta che la richiesta in corso (quando c'è) si sia
  // stabilizzata. L'elenco dei termini no: mostrarlo subito, indipendentemente
  // dalle proposte, è la correzione del difetto critico per cui una decisione
  // svuotava tutta la coda dietro un nuovo "Carico la coda…" a ogni tocco.
  const proposalsSettled =
    missingTermIds.length === 0 || proposalsQuery.isSuccess || proposalsQuery.isError;
  const proposalsFailed = proposalsQuery.isError;

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

  return (
    <Screen title="Ingredienti da abbinare">
      <p className="text-sm text-ink-soft">
        Ogni nome deciso vale per sempre, e le ricette che lo aspettavano entrano nel
        ricettario da sé.
      </p>

      {status && status.pending_recipes > 0 && (
        <p className="pt-1 text-xs text-ink-faint">
          {status.pending_recipes === 1
            ? "1 ricetta scaricata aspetta"
            : `${status.pending_recipes} ricette scaricate aspettano`}
          ,{" "}
          {status.imported === 1 ? "1 è già dentro" : `${status.imported} sono già dentro`}.
        </p>
      )}

      {lastUnlocked !== null && (
        <p className="pt-2 text-sm font-medium text-brand">
          {lastUnlocked === 0
            ? "Decisione registrata: nessuna ricetta era in attesa solo di questa."
            : lastUnlocked === 1
              ? "Sbloccata 1 ricetta."
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
        <Alert className="pt-2">{decisionErrorMessage(decide.error)}</Alert>
      )}

      {isLoading && <p className="pt-4 text-ink-soft">Carico la coda…</p>}

      {!isLoading && isError && (
        <Alert className="pt-4">
          Non sono riuscito a leggere la coda. Il ricettario funziona comunque: le
          ricette già importate sono al loro posto.
        </Alert>
      )}

      {!isLoading && !isError && terms.length === 0 && (
        <p className="pt-4 text-ink-soft">
          Niente da abbinare. Ogni ingrediente delle ricette scaricate ha la sua
          decisione.
        </p>
      )}

      {!isLoading && terms.length > 0 && (
        <ul className="flex flex-col gap-2 pt-2">
          {terms.map((term) => (
            <TermCard
              key={term.id}
              term={term}
              proposal={proposalsByTerm.get(term.id) ?? null}
              proposalsReady={proposalsSettled}
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

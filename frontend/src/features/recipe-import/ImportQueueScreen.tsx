import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError } from "../../api/client";
import { Alert } from "../../components/ui/Alert";
import { Screen } from "../../components/ui/Screen";
import { buttonClasses } from "../../components/ui/buttonClasses";
import { decideTerm, decideWithAi, fetchImportStatus, fetchImportTerms, undoTerm } from "./api";
import { DecidedTermRow } from "./DecidedTermRow";
import { TermCard, type Decision } from "./TermCard";

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
 *
 * L'AI decide in blocco su richiesta (`decideWithAi`), non termine per termine: le
 * sue decisioni si rivedono dall'elenco «Deciso dall'AI» qui sotto, ognuna con il
 * suo annulla, invece che come proposte da confermare una a una.
 */
export function ImportQueueScreen() {
  const queryClient = useQueryClient();
  const [lastUnlocked, setLastUnlocked] = useState<number | null>(null);

  const { data: terms = [], isLoading, isError } = useQuery({
    queryKey: ["import-terms"],
    queryFn: () => fetchImportTerms(),
  });

  const { data: status } = useQuery({
    queryKey: ["import-status"],
    queryFn: fetchImportStatus,
  });

  // Le decisioni dell'AI, le più recenti fra le ultime 50: il backend non ne
  // conta il totale, quindi il sottotitolo qui sotto lo dice invece di lasciare
  // credere che l'elenco sia tutta la storia.
  const { data: decided = [] } = useQuery({
    queryKey: ["import-terms", "ai"],
    queryFn: () => fetchImportTerms("ai"),
  });

  const [undoConfirm, setUndoConfirm] = useState<{ termId: string; message: string } | null>(
    null
  );

  const askAi = useMutation({
    mutationFn: () => decideWithAi(),
    onSuccess: (result) => {
      setLastUnlocked(result.unlocked);
      queryClient.invalidateQueries({ queryKey: ["import-terms"] });
      queryClient.invalidateQueries({ queryKey: ["import-status"] });
      queryClient.invalidateQueries({ queryKey: ["recipes"] });
    },
  });

  const undo = useMutation({
    mutationFn: ({ termId, force }: { termId: string; force: boolean }) =>
      undoTerm(termId, force),
    onSuccess: () => {
      setUndoConfirm(null);
      queryClient.invalidateQueries({ queryKey: ["import-terms"] });
      queryClient.invalidateQueries({ queryKey: ["import-status"] });
      queryClient.invalidateQueries({ queryKey: ["recipes"] });
    },
    onError: (error, variables) => {
      // Il 409 non è un guasto: è la conseguenza sullo storico di cottura, detta
      // prima. Il messaggio arriva dal backend col numero dentro, e mostrarlo è
      // l'unica cosa che permette di decidere se insistere.
      if (error instanceof ApiError && error.status === 409 && !variables.force) {
        setUndoConfirm({ termId: variables.termId, message: error.message });
      }
    },
  });

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

      {terms.length > 0 && (
        <button
          type="button"
          disabled={askAi.isPending}
          onClick={() => askAi.mutate()}
          className={buttonClasses("secondary", "block")}
        >
          {askAi.isPending ? "Sto chiedendo…" : "Riprova con l'AI"}
        </button>
      )}

      {askAi.isError && (
        <Alert className="pt-2">
          {askAi.error instanceof ApiError && askAi.error.status === 503
            ? askAi.error.message
            : "Non sono riuscito a chiedere all'AI. Decidi a mano: la coda funziona."}
        </Alert>
      )}

      {!isLoading && terms.length > 0 && (
        <ul className="flex flex-col gap-2 pt-2">
          {terms.map((term) => (
            <TermCard
              key={term.id}
              term={term}
              suggestionName={term.suggestion?.name ?? null}
              pending={decide.isPending}
              onDecide={(decision) => decide.mutate({ termId: term.id, decision })}
            />
          ))}
        </ul>
      )}

      {decided.length > 0 && (
        <section className="pt-6">
          <h2 className="text-sm font-medium text-ink-soft">Deciso dall'AI</h2>
          <p className="pt-1 text-xs text-ink-faint">
            Le 50 decisioni più recenti, non tutte quelle prese. Ogni riga si può
            annullare: il termine torna in coda e le ricette che ne erano nate si
            rifanno.
          </p>
          <ul className="pt-2">
            {decided.map((term) => (
              <DecidedTermRow
                key={term.id}
                term={term}
                pending={undo.isPending}
                onUndo={() => undo.mutate({ termId: term.id, force: false })}
              />
            ))}
          </ul>
        </section>
      )}

      {undoConfirm && (
        <div role="alertdialog" aria-label="Conferma l'annullamento" className="pt-3">
          <Alert>{undoConfirm.message}</Alert>
          <div className="flex gap-2 pt-2">
            <button
              type="button"
              disabled={undo.isPending}
              onClick={() => undo.mutate({ termId: undoConfirm.termId, force: true })}
              className={buttonClasses("primary", "pill")}
            >
              Rifai comunque
            </button>
            <button
              type="button"
              onClick={() => setUndoConfirm(null)}
              className={buttonClasses("ghost", "pill")}
            >
              Lascia com'è
            </button>
          </div>
        </div>
      )}
    </Screen>
  );
}

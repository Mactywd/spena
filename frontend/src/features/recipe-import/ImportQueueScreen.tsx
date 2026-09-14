import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError } from "../../api/client";
import { Alert } from "../../components/ui/Alert";
import { Screen } from "../../components/ui/Screen";
import { buttonClasses } from "../../components/ui/buttonClasses";
import type { DecideResult } from "../../domain/types";
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

/** Il messaggio da mostrare quando annullare una decisione fallisce per davvero.
 *
 * Il 409 che chiede conferma («ci sono ricette già cucinate») non passa da qui: lo
 * gestisce `undoConfirm`, col suo dialogo. Da qui passano solo i rifiuti veri —
 * compreso lo stesso 409 quando torna con `force` già a `true`, perché a quel punto
 * non è più una domanda: il backend rifiuta perché il termine è già in coda (non
 * c'è niente da disfare), un fatto che `force` non supera mai. Il suo `detail` dice
 * perché, ed è un 4xx come quello di `decisionErrorMessage` — stessa forma, stesso
 * motivo per mostrarlo verbatim.
 */
function undoErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.status >= 400 && error.status < 500) {
    return error.message;
  }
  return "Non sono riuscito ad annullare la decisione. Niente è andato perso: riprova.";
}

/** Cosa dire dopo un giro dell'AI sulla coda.
 *
 * `applied` conta le decisioni prese in QUESTO giro; `still_pending` quante delle
 * proposte il modello non ha saputo giudicare. Uno zero in `applied` letto come "il
 * bottone non ha fatto niente" spinge a ripremerlo — un'altra chiamata a pagamento —
 * quando invece l'AI è girata e ha rinunciato su tutto quel che le era davanti: la
 * frase lo dice chiaro, e dice anche che i termini restano decidibili a mano qui
 * sotto, che è la via d'uscita che "mai un vicolo cieco" richiede.
 */
function aiRunMessage(result: DecideResult): string {
  const unlockedPart =
    result.unlocked === 0
      ? "Nessuna ricetta era in attesa solo di queste decisioni."
      : result.unlocked === 1
        ? "Sbloccata 1 ricetta."
        : `Sbloccate ${result.unlocked} ricette.`;

  if (result.applied === 0) {
    return result.still_pending === 1
      ? "L'AI ha risposto ma non ha deciso il termine che le hai sottoposto: resta in coda, e si decide a mano qui sotto. Riprovare con l'AI costa un'altra chiamata al modello."
      : `L'AI ha risposto ma non ha deciso nessuno dei ${result.still_pending} termini che le hai sottoposto: restano in coda, e si decidono a mano qui sotto. Riprovare con l'AI costa un'altra chiamata al modello.`;
  }

  if (result.still_pending === 0) {
    return `L'AI ha deciso tutti i termini che le hai sottoposto. ${unlockedPart}`;
  }

  const decisePart = result.applied === 1 ? "L'AI ha deciso 1 termine" : `L'AI ha deciso ${result.applied} termini`;
  const pendingPart =
    result.still_pending === 1
      ? "1 resta in coda: non l'ha saputo giudicare."
      : `${result.still_pending} restano in coda: non li ha saputi giudicare.`;
  return `${decisePart}, ${pendingPart} ${unlockedPart}`;
}

/** L'esito di un annullamento riuscito: quante ricette sono tornate in coda, e se
 * ha cancellato l'ingrediente che quella decisione aveva creato. Il secondo fatto è
 * l'unica cosa che dice cosa è stato distrutto dall'unica conferma distruttiva di
 * questa funzione ("Rifai comunque"): senza dirlo qui, si scopre solo tornando
 * nell'anagrafica.
 */
function undoResultMessage({
  recipesRequeued,
  ingredientDeleted,
}: {
  recipesRequeued: number;
  ingredientDeleted: boolean;
}): string {
  const recipesPart =
    recipesRequeued === 0
      ? "Nessuna ricetta è tornata in coda."
      : recipesRequeued === 1
        ? "1 ricetta è tornata in coda."
        : `${recipesRequeued} ricette sono tornate in coda.`;
  return ingredientDeleted
    ? `${recipesPart} L'ingrediente che questa decisione aveva creato è stato eliminato, perché nessun'altra cosa lo usava.`
    : recipesPart;
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
// Che una decisione l'abbia presa una persona o l'AI in blocco cambia cosa c'è da
// dire dopo: una sola frase condivisa tra le due o mostrerebbe contatori dell'AI
// dopo un tocco a mano, o appiattirebbe un giro dell'AI alla sola frase sbloccata,
// perdendo esattamente la distinzione che il punto 2 della revisione chiede.
type LastRun = { kind: "manual"; unlocked: number } | { kind: "ai"; result: DecideResult };

export function ImportQueueScreen() {
  const queryClient = useQueryClient();
  const [lastRun, setLastRun] = useState<LastRun | null>(null);
  const [lastUndo, setLastUndo] = useState<{
    recipesRequeued: number;
    ingredientDeleted: boolean;
  } | null>(null);
  const [undoError, setUndoError] = useState<string | null>(null);

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
      setLastRun({ kind: "ai", result });
      // un giro nuovo scavalca l'esito di un annullamento precedente: i due
      // messaggi condividono lo stesso angolo di schermo, e lasciarli entrambi
      // farebbe leggere un annullamento vecchio come l'esito di questo giro
      setLastUndo(null);
      queryClient.invalidateQueries({ queryKey: ["import-terms"] });
      queryClient.invalidateQueries({ queryKey: ["import-status"] });
      queryClient.invalidateQueries({ queryKey: ["recipes"] });
    },
  });

  const undo = useMutation({
    mutationFn: ({ termId, force }: { termId: string; force: boolean }) =>
      undoTerm(termId, force),
    onMutate: () => {
      // un nuovo tentativo non deve restare sull'errore del precedente: senza
      // questo, annullare un secondo termine con successo lascerebbe in vista
      // l'alert del primo tentativo fallito
      setUndoError(null);
    },
    onSuccess: (result) => {
      setUndoConfirm(null);
      setLastUndo({
        recipesRequeued: result.recipes_requeued,
        ingredientDeleted: result.ingredient_deleted,
      });
      setLastRun(null);
      queryClient.invalidateQueries({ queryKey: ["import-terms"] });
      queryClient.invalidateQueries({ queryKey: ["import-status"] });
      queryClient.invalidateQueries({ queryKey: ["recipes"] });
    },
    onError: (error, variables) => {
      // Il 409 senza `force` non è un guasto: è la conseguenza sullo storico di
      // cottura, detta prima che si applichi niente. Il messaggio arriva dal
      // backend col numero dentro, e mostrarlo nel dialogo è l'unica cosa che
      // permette di decidere se insistere.
      if (error instanceof ApiError && error.status === 409 && !variables.force) {
        setUndoConfirm({ termId: variables.termId, message: error.message });
        return;
      }
      // Ogni altro esito è un rifiuto vero, non una domanda: il 409 che torna
      // *con* `force` già a `true` (il termine è di nuovo in coda, o lo era già —
      // il backend controlla questo prima di guardare `force`, quindi insistere
      // non lo supera mai) tanto quanto un 500 o una rete caduta. Il dialogo si
      // chiude perché non c'è più niente da confermare, e l'errore si vede: senza
      // questo, il tocco sembra ignorato e l'unica uscita resta "Lascia com'è" —
      // l'anello infinito che `force` esiste per evitare, raggiunto da un'altra
      // porta.
      setUndoConfirm(null);
      setUndoError(undoErrorMessage(error));
    },
  });

  const decide = useMutation({
    mutationFn: ({ termId, decision }: { termId: string; decision: Decision }) =>
      decideTerm(termId, decision),
    onSuccess: (result) => {
      setLastRun({ kind: "manual", unlocked: result.unlocked });
      setLastUndo(null);
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

      {lastRun?.kind === "manual" && (
        <p className="pt-2 text-sm font-medium text-brand">
          {lastRun.unlocked === 0
            ? "Decisione registrata: nessuna ricetta era in attesa solo di questa."
            : lastRun.unlocked === 1
              ? "Sbloccata 1 ricetta."
              : `Sbloccate ${lastRun.unlocked} ricette.`}
        </p>
      )}

      {lastRun?.kind === "ai" && (
        <p className="pt-2 text-sm font-medium text-brand">{aiRunMessage(lastRun.result)}</p>
      )}

      {lastUndo && (
        <p className="pt-2 text-sm font-medium text-brand">{undoResultMessage(lastUndo)}</p>
      )}

      {decide.isError && (
        <Alert className="pt-2">{decisionErrorMessage(decide.error)}</Alert>
      )}

      {undoError && <Alert className="pt-2">{undoError}</Alert>}

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
            Le decisioni più recenti, non tutte quelle prese. Ogni riga si può
            annullare: il termine torna in coda, le ricette che ne erano nate si
            rifanno, e se questa decisione aveva creato un ingrediente nuovo
            l'annullamento lo cancella, sempre che nient'altro lo usi nel
            frattempo.
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

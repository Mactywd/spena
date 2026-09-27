import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { ApiError } from "../../api/client";
import { defaultQueryRetryPredicate } from "../../lib/queryRetry";
import { Alert } from "../../components/ui/Alert";
import { Screen } from "../../components/ui/Screen";
import { buttonClasses } from "../../components/ui/buttonClasses";
import type { DecideResult, ImportTerm } from "../../domain/types";
import {
  decideTerm,
  decideWithAi,
  fetchImportStatus,
  fetchImportTerm,
  fetchImportTerms,
  undoTerm,
} from "./api";
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

/** Il messaggio da mostrare quando annullare una decisione fallisce.
 *
 * Dalla S9 non c'è più un 409 che chiede conferma: le cotture delle ricette rifatte
 * si ri-legano, quindi annullare non scollega niente. Da qui passano i rifiuti veri —
 * il 409 del termine già in coda, che nel suo `detail` dice perché — e i guasti. È un
 * 4xx come quello di `decisionErrorMessage`: stessa forma, stesso motivo per
 * mostrarlo verbatim.
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
 * ha cancellato l'ingrediente che quella decisione aveva creato. Dal 2026-09-28 il
 * backend non ne cancella più nessuno (`undo_decision`: `mapped` non distingue un
 * ingrediente creato da uno che c'era già) e `ingredient_deleted` è sempre falso; il
 * ramo resta perché la frase è vera se mai tornasse vero.
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

/** Quante decisioni recenti mostra l'elenco: lo stesso tetto che `fetchImportTerms`
 * chiede per ciascun autore. */
const RECENT_DECISIONS_LIMIT = 50;

/** Le decisioni dell'AI e quelle a mano in un elenco solo, dalla più recente.
 *
 * Ciascun elenco arriva già ordinato e tagliato a 50 dal backend; fusi, se ne
 * tengono di nuovo 50, così il tetto resta quello di prima e non raddoppia. Le 50
 * più recenti dell'unione stanno per forza fra le 50 più recenti di ciascun autore,
 * quindi il taglio non perde niente che dovrebbe vedersi. Una decisione senza data
 * (le più vecchie potrebbero non averla) va in fondo, come la mette il backend.
 */
function recentDecisions(byAi: ImportTerm[], byHand: ImportTerm[]): ImportTerm[] {
  const time = (term: ImportTerm) =>
    term.decided_at === null ? Number.NEGATIVE_INFINITY : Date.parse(term.decided_at);
  return [...byAi, ...byHand]
    .sort(
      (a, b) => time(b) - time(a) || a.display_name.localeCompare(b.display_name, "it")
    )
    .slice(0, RECENT_DECISIONS_LIMIT);
}

/** La revisione dei termini dell'import.
 *
 * Una decisione per volta, e ogni decisione materializza subito le ricette che
 * aspettavano quel termine: il numero che torna è ciò che rende questa schermata un
 * lavoro con un risultato visibile invece di un modulo da compilare.
 *
 * L'AI decide in blocco su richiesta (`decideWithAi`), non termine per termine: le
 * sue decisioni si rivedono dall'elenco «Decisioni recenti» qui sotto, ognuna con il
 * suo annulla, invece che come proposte da confermare una a una. Nello stesso elenco
 * stanno le decisioni prese a mano, con lo stesso annulla (R11): si sbagliano
 * altrettanto, e una decisione a mano che sparisse dalla schermata si correggerebbe
 * solo dall'anagrafica.
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

  const { data: queue = [], isLoading, isError } = useQuery({
    queryKey: ["import-terms"],
    queryFn: () => fetchImportTerms(),
  });

  // `?termine=<id>`: il termine a cui porta un rifiuto dell'anagrafica («annullalo in
  // coda»). Si legge per id e non si cerca fra quelli caricati: «Decisioni recenti»
  // ne tiene al più cento e nessuno deciso `auto`, e un termine deciso tempo fa non
  // ci sarebbe. Sotto la chiave `import-terms`, così ogni decisione e ogni
  // annullamento lo rileggono, e dopo un annulla la stessa riga diventa la scheda
  // per decidere di nuovo.
  const [searchParams] = useSearchParams();
  const focusId = searchParams.get("termine");
  const focus = useQuery({
    queryKey: ["import-terms", "focus", focusId],
    queryFn: () => fetchImportTerm(focusId ?? ""),
    enabled: focusId !== null,
    // un 404 è già la risposta — quel termine non c'è — e ritentarlo terrebbe la riga
    // che lo dice fuori vista per secondi; il resto si ritenta come ovunque
    retry: (count, error) =>
      !(error instanceof ApiError && error.status === 404) &&
      defaultQueryRetryPredicate(count, error),
  });
  const focused = focus.data ?? null;
  // una volta in cima, non anche più sotto: due schede dello stesso termine
  const terms = queue.filter((term) => term.id !== focused?.id);

  const { data: status } = useQuery({
    queryKey: ["import-status"],
    queryFn: fetchImportStatus,
  });

  // Le decisioni dell'AI e quelle a mano, le 50 più recenti di ciascuna: il
  // backend non ne conta il totale, quindi il sottotitolo qui sotto lo dice invece
  // di lasciare credere che l'elenco sia tutta la storia. Due richieste e non una
  // perché la rotta filtra per un autore solo; un guasto di una delle due lascia
  // comunque l'altra in vista.
  const { data: decidedByAi = [] } = useQuery({
    queryKey: ["import-terms", "ai"],
    queryFn: () => fetchImportTerms("ai"),
  });
  const { data: decidedByHand = [] } = useQuery({
    queryKey: ["import-terms", "human"],
    queryFn: () => fetchImportTerms("human"),
  });
  const decided = recentDecisions(decidedByAi, decidedByHand).filter(
    (term) => term.id !== focused?.id
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
    mutationFn: (termId: string) => undoTerm(termId),
    onMutate: () => {
      // un nuovo tentativo non deve restare sull'errore del precedente: senza
      // questo, annullare un secondo termine con successo lascerebbe in vista
      // l'alert del primo tentativo fallito
      setUndoError(null);
    },
    onSuccess: (result) => {
      setLastUndo({
        recipesRequeued: result.recipes_requeued,
        ingredientDeleted: result.ingredient_deleted,
      });
      setLastRun(null);
      queryClient.invalidateQueries({ queryKey: ["import-terms"] });
      queryClient.invalidateQueries({ queryKey: ["import-status"] });
      queryClient.invalidateQueries({ queryKey: ["recipes"] });
    },
    // ogni esito diverso dal successo è un rifiuto vero, e si vede
    onError: (error) => setUndoError(undoErrorMessage(error)),
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
    <Screen title="Ingredienti da abbinare" back={{ to: "/ricette", label: "Ricette" }}>
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

      {focused && (
        <section aria-labelledby="termine-a-fuoco" className="pt-4">
          <h2 id="termine-a-fuoco" className="text-sm font-medium text-ink-soft">
            Il termine che cercavi
          </h2>
          <ul className="pt-2">
            {focused.decided_action === null ? (
              <TermCard
                key={`${focused.id}-in-coda`}
                term={focused}
                suggestionName={focused.suggestion?.name ?? null}
                pending={decide.isPending}
                onDecide={(decision) => decide.mutate({ termId: focused.id, decision })}
              />
            ) : (
              <DecidedTermRow
                term={focused}
                pending={undo.isPending}
                onUndo={() => undo.mutate(focused.id)}
              />
            )}
          </ul>
        </section>
      )}

      {focusId !== null && focus.isError && (
        <p className="pt-2 text-sm text-ink-soft">
          Non trovo quel termine. La coda e le decisioni recenti sono qui sotto.
        </p>
      )}

      {isLoading && <p className="pt-4 text-ink-soft">Carico la coda…</p>}

      {!isLoading && isError && (
        <Alert className="pt-4">
          Non sono riuscito a leggere la coda. Il ricettario funziona comunque: le
          ricette già importate sono al loro posto.
        </Alert>
      )}

      {!isLoading && !isError && queue.length === 0 && (
        <p className="pt-4 text-ink-soft">
          Niente da abbinare. Ogni ingrediente delle ricette scaricate ha la sua
          decisione.
        </p>
      )}

      {queue.length > 0 && (
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
          <h2 className="text-sm font-medium text-ink-soft">Decisioni recenti</h2>
          <p className="pt-1 text-xs text-ink-faint">
            Le più recenti, tue e dell'AI, non tutte quelle prese. Ogni riga si può
            annullare: il termine torna in coda, le ricette che ne erano nate si
            rifanno, e l'ingrediente a cui puntava resta in anagrafica, anche se
            l'aveva creato questa decisione.
          </p>
          <ul className="pt-2">
            {decided.map((term) => (
              <DecidedTermRow
                key={term.id}
                term={term}
                pending={undo.isPending}
                onUndo={() => undo.mutate(term.id)}
              />
            ))}
          </ul>
        </section>
      )}
    </Screen>
  );
}

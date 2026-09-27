import { buttonClasses } from "../../components/ui/buttonClasses";
import type { ImportTerm } from "../../domain/types";

/** Cosa è stato fatto di questo termine, in una frase.
 *
 * «Rigatoni → pasta» e non «mappato con successo»: il nome dell'ingrediente è la sola
 * informazione su cui si può giudicare se la decisione è giusta, e nasconderla dietro
 * un verbo tecnico renderebbe la revisione una lista di caselle da spuntare.
 *
 * Un termine accorpato dal collasso non ha niente di speciale: è un aggancio, e si
 * mostra come un aggancio, perché è quello che è.
 */
/** Chi ha deciso, in una parola: «AI» o «tu».
 *
 * Le decisioni dell'AI e quelle a mano stanno nello stesso elenco (R11), e sbagliano
 * per motivi diversi: senza l'etichetta, un collegamento sbagliato fatto a mano si
 * leggerebbe come un errore del modello. La parola visibile è corta per stare sulla
 * riga di un telefono; chi ascolta sente la frase intera, perché «tu» da solo, letto
 * accanto al nome del termine, non dice niente.
 */
function DecidedByLabel({ decidedBy }: { decidedBy: string | null }) {
  const human = decidedBy === "human";
  return (
    <>
      <span
        data-testid="decided-by"
        aria-hidden="true"
        className="shrink-0 rounded-full border border-line bg-card px-2 py-0.5 text-xs font-medium text-ink-soft"
      >
        {human ? "tu" : "AI"}
      </span>
      <span className="sr-only">{human ? "deciso da te" : "deciso dall'AI"}</span>
    </>
  );
}

function decisionSummary(term: ImportTerm): string {
  if (term.decided_action === "ignored") return "ignorato: non si tiene in dispensa";
  // «creato» solo quando la decisione l'ha scritto; le decisioni di prima non lo
  // sanno, e «collegato» non promette niente in più
  if (term.created_ingredient === true) return `creato: ${term.decided_name ?? "un ingrediente"}`;
  return `collegato a ${term.decided_name ?? "un ingrediente"}`;
}

export function DecidedTermRow({
  term,
  pending,
  onUndo,
}: {
  term: ImportTerm;
  pending: boolean;
  onUndo: () => void;
}) {
  return (
    <li className="flex items-center justify-between gap-3 border-b border-line py-3 last:border-b-0">
      <div className="min-w-0">
        <div className="flex min-w-0 items-center gap-2">
          <p className="truncate font-medium">{term.display_name}</p>
          <DecidedByLabel decidedBy={term.decided_by} />
        </div>
        <p className="truncate text-xs text-ink-soft">{decisionSummary(term)}</p>
      </div>
      {/* il nome accessibile porta il termine: una riga per termine, e senza il nome
          chi ascolta sente N pulsanti «Annulla» indistinguibili */}
      <button
        type="button"
        disabled={pending}
        onClick={onUndo}
        aria-label={`Annulla la decisione su «${term.display_name}»`}
        className={buttonClasses("ghost", "pill")}
      >
        Annulla
      </button>
    </li>
  );
}

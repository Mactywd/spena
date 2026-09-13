import { buttonClasses } from "../../components/ui/buttonClasses";
import type { ImportTerm } from "../../domain/types";

/** Cosa l'AI ha fatto di questo termine, in una frase.
 *
 * «Rigatoni → pasta» e non «mappato con successo»: il nome dell'ingrediente è la sola
 * informazione su cui si può giudicare se la decisione è giusta, e nasconderla dietro
 * un verbo tecnico renderebbe la revisione una lista di caselle da spuntare.
 *
 * Un termine accorpato dal collasso non ha niente di speciale: è un aggancio, e si
 * mostra come un aggancio, perché è quello che è.
 */
function decisionSummary(term: ImportTerm): string {
  if (term.decided_action === "ignored") return "ignorato: non si tiene in dispensa";
  if (term.decided_action === "created") return `creato: ${term.decided_name ?? "—"}`;
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
        <p className="truncate font-medium">{term.display_name}</p>
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

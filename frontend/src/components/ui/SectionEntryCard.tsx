import { Link } from "react-router-dom";

/** L'ingresso a una sottosezione, in cima alla sezione madre.
 *
 * Chi la usa decide quando c'è. In Lista e Dispensa, «Sistema la spesa» è sempre
 * presente (D3 di docs/prossimi-passi.md): sparire quando non c'è niente da fare la
 * renderebbe irraggiungibile proprio quando la si vuole visitare apposta, per sistemare
 * una spesa che non si è spuntata. Nel ricettario «Ingredienti da abbinare» compare solo
 * con la coda non vuota (T3 Consegna 4, spec §4.5): lì la sottosezione ha un'altra porta
 * che c'è sempre, la voce del ☰, e da lì si rivedono le decisioni già prese.
 *
 * L'ambra è lo stesso colore di «quasi finito»: nell'app vuol dire «c'è qualcosa
 * che ti riguarda», non «è andato male qualcosa». Il pallino è decorazione e basta:
 * il messaggio lo porta la nota, che si legge anche con la voce.
 */
export function SectionEntryCard({
  to,
  title,
  note,
  pending = false,
}: {
  to: string;
  title: string;
  /** che cosa c'è da fare, o perché non c'è niente: mai vuota */
  note: string;
  pending?: boolean;
}) {
  return (
    <Link
      to={to}
      className={`mb-3 flex min-h-14 items-center justify-between gap-3 rounded-card px-3.5 py-2.5 ${
        pending ? "bg-low-tint text-low" : "bg-card text-ink"
      }`}
    >
      <span className="min-w-0">
        <span className="flex items-center gap-2 font-medium">
          {pending && (
            <span aria-hidden="true" className="size-2 shrink-0 rounded-full bg-low" />
          )}
          {title}
        </span>
        <span className={`block truncate text-sm ${pending ? "text-low" : "text-ink-soft"}`}>
          {note}
        </span>
      </span>
      <span aria-hidden="true" className="shrink-0">›</span>
    </Link>
  );
}

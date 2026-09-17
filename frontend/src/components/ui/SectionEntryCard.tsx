import { Link } from "react-router-dom";

/** L'ingresso a una sottosezione, in cima alla sezione madre.
 *
 * Sempre presente (D3 di docs/prossimi-passi.md). Sparire quando non c'è niente da
 * fare è ciò che rende una sottosezione irraggiungibile proprio quando la si vuole
 * visitare apposta — per sistemare una spesa che non si è spuntata, per rivedere
 * una decisione già presa.
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

import { Link } from "react-router-dom";

/** Il ritorno dalla sottosezione alla sezione madre.
 *
 * Una destinazione dichiarata, non `navigate(-1)`. In una PWA installata su iOS il
 * tasto indietro del telefono non c'è, e la cronologia può essere vuota: ci si
 * arriva da un collegamento condiviso, o da una schermata che il sistema ha
 * riaperto. Lì `-1` non torna alla sezione madre — esce dall'app, o non fa niente.
 * Sapere dove si torna è compito di chi rende lo schermo, e costa una parola.
 */
export function BackLink({ to, label }: { to: string; label: string }) {
  return (
    <Link
      to={to}
      className="-ml-1 inline-flex min-h-11 items-center gap-1 text-sm font-medium text-ink-soft"
    >
      <span aria-hidden="true">‹</span>
      {label}
    </Link>
  );
}

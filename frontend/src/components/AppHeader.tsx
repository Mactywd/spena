import { Link } from "react-router-dom";

// Il segno dell'app, disegnato qui come le tre icone della TabBar e per lo stesso
// motivo: una libreria di icone peserebbe sul primo avvio di una PWA più di quanto
// valga, e di marchi ce n'è uno. Una pentola con il vapore: solo tratti, nessun
// riempimento, `currentColor` così eredita il verde del nome accanto.
function Mark() {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      className="size-6"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M3.5 10.5h17v4.5a4.5 4.5 0 0 1-4.5 4.5H8a4.5 4.5 0 0 1-4.5-4.5z" />
      <path d="M20.5 12h1a1.8 1.8 0 0 1 0 3.6h-1" />
      <path d="M9.5 7.5c0-1.2 1-1.6 1-2.8M14 7.5c0-1.2 1-1.6 1-2.8" />
    </svg>
  );
}

/** L'intestazione che sta sopra ogni schermata.
 *
 * `sticky` e non `fixed`: fissa, dovrebbe riservarsi lo spazio con un margine sul
 * contenuto, e quel margine si dimentica il giorno in cui l'altezza cambia.
 *
 * A destra non c'è niente, ed è una scelta: l'hamburger dell'indice completo
 * (T1 di docs/prossimi-passi.md) arriva quando esisterà la prima sezione
 * secondaria da indicizzare. Un menu che ripete le tre schede della barra in
 * basso non è un indice.
 */
export function AppHeader() {
  return (
    <header role="banner" className="sticky top-0 z-10 h-12 border-b border-line bg-card">
      {/* l'altezza sta sull'header, non su questo div: il bordo dell'header è nella
          sua stessa scatola (box-sizing: border-box, dal preflight di Tailwind), e
          49px (48 + 1 di bordo) contro i 48 che `main` riserva con
          `calc(100dvh-3rem)` sono la differenza verticale che frontend/e2e/style.spec.ts
          ora controlla e che qui misurava un pixel di scorrimento in più */}
      <div className="mx-auto flex h-full max-w-md items-center px-4">
        <Link
          to="/"
          className="flex min-h-11 items-center gap-2 font-semibold tracking-tight text-brand"
        >
          <Mark />
          Spena
        </Link>
      </div>
    </header>
  );
}

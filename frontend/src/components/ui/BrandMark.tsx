// Il cesto: il marchio dell'app, uno solo (spec T3 §3.4). È lo stesso disegno della
// favicon e delle icone della PWA, così chi apre l'app ritrova il segno che ha toccato
// sulla schermata iniziale. Resta un SVG disegnato a mano: la libreria di icone serve
// alle azioni, non al marchio.
export function BrandMark({ className = "size-7" }: { className?: string }) {
  return (
    <svg viewBox="0 0 512 512" aria-hidden="true" data-mark="cesto" className={className}>
      <rect width="512" height="512" rx="112" fill="var(--color-brand)" />
      <g fill="none" stroke="var(--color-on-brand)" strokeLinecap="round" strokeLinejoin="round">
        <path d="M148 218h216l-42 142H190z" strokeWidth="26" />
        <path d="M194 218a62 62 0 0 1 124 0" strokeWidth="26" />
        <path d="M219 254l9 76M293 254l-9 76" strokeWidth="22" />
      </g>
    </svg>
  );
}

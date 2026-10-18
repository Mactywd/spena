export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "warn";
export type ButtonShape = "pill" | "block" | "icon" | "square";

// Le classi dei bottoni, non un componente: servono anche a dei `<Link>` (il «Sistema
// la spesa» della lista è una navigazione, non un'azione) e un componente polimorfo
// per coprire i due casi costerebbe più di quanto rende. Sta in un file suo perché
// accanto a un componente un export costante rompe il fast refresh.
//
// `min-h-11` è la regola di casa sui bersagli da pollice: 44px è il minimo che si
// tocca camminando, con una mano, senza sbagliare la riga. Vive qui una volta invece
// che in trenta posti dove dimenticarlo è gratis.
//
// Lo spento, per ogni variante e per i tre modi di spegnere — `disabled`, e in `Button`
// `busy` e `unavailableReason`, che spengono con `aria-disabled` per tenere il fuoco — è
// un colore pieno per tema, non un'`opacity`. L'`opacity` 0,4 componeva fondo e scritta
// con quel che c'era dietro, e portava ogni variante sotto 4,5:1: in chiaro il primario a
// 1,8:1, in scuro un verde torbido (bozza del tema scuro, 2026-10-06, decisa il
// 2026-10-07). Un fondo pieno spento diventa il grigio `disabled` con la sua scritta
// `on-disabled`, perché un verde o un'ambra attenuati direbbero ancora «azione
// principale» o «risolvi il problema»; chi non ha fondo scrive in `ink-faint`. Lo stesso
// elenco sotto `disabled:` e sotto `aria-disabled:`: un pulsante in volo deve sembrare
// spento come uno spento davvero. Le classi con prefisso vincono su `bg-brand` perché
// Tailwind scrive le varianti dopo le utilità semplici nel CSS compilato: lo misura
// e2e/style.spec.ts, non jsdom.
const BASE = "inline-flex min-h-11 items-center justify-center gap-2 font-medium transition-colors";

const OFF_FILLED =
  "disabled:bg-disabled disabled:text-on-disabled aria-disabled:bg-disabled aria-disabled:text-on-disabled";
const OFF_TEXT = "disabled:text-ink-faint aria-disabled:text-ink-faint";

const VARIANTS: Record<ButtonVariant, string> = {
  primary: `bg-brand text-on-brand ${OFF_FILLED}`,
  // spento resta l'anello `line`: è la forma del secondario, non il suo colore
  secondary: `bg-card text-ink ring-1 ring-line ring-inset ${OFF_TEXT}`,
  // ambra: lo stesso colore del problema che questo bottone risolve
  warn: `bg-low text-on-low ${OFF_FILLED}`,
  ghost: `text-ink-soft ${OFF_TEXT}`,
  danger: `text-danger ${OFF_TEXT}`,
};

const SHAPES: Record<ButtonShape, string> = {
  pill: "rounded-full px-4 text-sm",
  // a tutta larghezza la pastiglia sembra un errore di misura: il raggio delle schede
  block: "w-full rounded-card px-4 py-3 text-base",
  // di sola icona (spec T3 §2): un quadrato da 44px, il bersaglio minimo di casa
  icon: "size-11 shrink-0 rounded-full",
  // lo stesso bersaglio con gli angoli dei pulsanti (spec T3 §3.2, 10–12 px): il + della
  // barra in cima, che sta accanto a un campo e ne riprende la forma. Una forma sua e
  // non un `rounded-[10px]` aggiunto a `icon`: fra due raggi sullo stesso elemento
  // decide l'ordine del CSS compilato, e vinceva il cerchio
  square: "size-11 shrink-0 rounded-[10px]",
};

export function buttonClasses(variant: ButtonVariant = "secondary", shape: ButtonShape = "pill"): string {
  return `${BASE} ${SHAPES[shape]} ${VARIANTS[variant]}`;
}

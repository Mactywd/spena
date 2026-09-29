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
// `aria-disabled:opacity-40` accanto a `disabled:opacity-40`: un pulsante in volo
// (`busy` in Button) si spegne con `aria-disabled` per tenere il fuoco, e deve
// sembrare spento come uno spento davvero
const BASE =
  "inline-flex min-h-11 items-center justify-center gap-2 font-medium transition-colors disabled:opacity-40 aria-disabled:opacity-40";

const VARIANTS: Record<ButtonVariant, string> = {
  primary: "bg-brand text-on-brand",
  secondary: "bg-card text-ink ring-1 ring-line ring-inset",
  // ambra: lo stesso colore del problema che questo bottone risolve
  warn: "bg-low text-on-low",
  ghost: "text-ink-soft",
  danger: "text-danger",
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

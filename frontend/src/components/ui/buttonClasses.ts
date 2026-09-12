type Variant = "primary" | "secondary" | "ghost" | "danger" | "warn";
type Shape = "pill" | "block";

// Le classi dei bottoni, non un componente: servono anche a dei `<Link>` (il «Sistema
// la spesa» della lista è una navigazione, non un'azione) e un componente polimorfo
// per coprire i due casi costerebbe più di quanto rende. Sta in un file suo perché
// accanto a un componente un export costante rompe il fast refresh.
//
// `min-h-11` è la regola di casa sui bersagli da pollice: 44px è il minimo che si
// tocca camminando, con una mano, senza sbagliare la riga. Vive qui una volta invece
// che in trenta posti dove dimenticarlo è gratis.
const BASE = "inline-flex min-h-11 items-center justify-center gap-2 font-medium transition-colors disabled:opacity-40";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-brand text-white",
  secondary: "bg-card text-ink ring-1 ring-line ring-inset",
  // ambra: lo stesso colore del problema che questo bottone risolve
  warn: "bg-low text-white",
  ghost: "text-ink-soft",
  danger: "text-danger",
};

const SHAPES: Record<Shape, string> = {
  pill: "rounded-full px-4 text-sm",
  // a tutta larghezza la pastiglia sembra un errore di misura: il raggio delle schede
  block: "w-full rounded-card px-4 py-3 text-base",
};

export function buttonClasses(variant: Variant = "secondary", shape: Shape = "pill"): string {
  return `${BASE} ${SHAPES[shape]} ${VARIANTS[variant]}`;
}

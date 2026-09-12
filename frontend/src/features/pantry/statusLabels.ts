import type { PantryStatus } from "../../domain/types";

// Le tre parole con cui il sistema chiama gli stati, in un posto solo: StatusToggle
// le usa come scelte in dispensa, il foglio di cottura per dire in che stato è una
// confezione adesso. Due vocabolari per la stessa cosa confonderebbero chi passa da
// uno schermo all'altro. Sta in un file suo perché accanto a un componente un
// export costante rompe il fast refresh.
export const STATUS_LABELS: Record<PantryStatus, string> = {
  available: "Disponibile",
  low: "Quasi finito",
  finished: "Finito",
};

/** I due modi in cui una pastiglia porta il colore di uno stato. */
export type StatusTone = {
  /** pieno, per la scelta attiva: il colore è il messaggio */
  fill: string;
  /** tinta leggera, per dire solo com'è adesso senza chiedere niente */
  tint: string;
};

// Il colore degli stati sta accanto alle loro parole, e per lo stesso motivo: la
// dispensa e il foglio di cottura parlano degli stessi tre stati, e due mappe
// separate divergono. Questa è l'unica sorgente di verità sul colore di uno stato.
//
// `low` non è una sfumatura del verde: è l'unico stato che cambia la risposta alla
// domanda «si può cucinare?», e prima di questa mappa era verde identico a
// `available`, cioè invisibile.
export const STATUS_TONE: Record<PantryStatus, StatusTone> = {
  available: { fill: "bg-brand text-white", tint: "bg-brand-tint text-brand" },
  low: { fill: "bg-low text-white", tint: "bg-low-tint text-low" },
  finished: { fill: "bg-ink text-white", tint: "bg-page text-ink-soft" },
};

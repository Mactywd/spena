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

import { Chip } from "./Chip";
import { STATUS_LABELS, STATUS_TONE } from "../../features/pantry/statusLabels";
import type { PantryStatus } from "../../domain/types";

// Lo stato quando si legge e non si tocca: in tinta leggera, non piena. Il pieno è
// riservato alla scelta attiva dei pulsanti di stato del foglio di cottura
// (CookSheet), così il colore acceso significa sempre «questo l'hai deciso tu
// adesso» e non «questa è la situazione». In dispensa si decide col FillSlider, e
// questa pastiglia accanto dice soltanto com'è andata.
export function StatusChip({ status }: { status: PantryStatus }) {
  return <Chip tone={STATUS_TONE[status].tint}>{STATUS_LABELS[status]}</Chip>;
}

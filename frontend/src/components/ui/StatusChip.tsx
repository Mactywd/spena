import { STATUS_LABELS, STATUS_TONE } from "../../features/pantry/statusLabels";
import type { PantryStatus } from "../../domain/types";

// Lo stato quando si legge e non si tocca: in tinta leggera, non piena. Il pieno è
// riservato alla scelta attiva dello StatusToggle, così il colore acceso significa
// sempre «questo l'hai deciso tu adesso» e non «questa è la situazione».
export function StatusChip({ status }: { status: PantryStatus }) {
  return (
    <span
      className={`inline-block rounded-full px-2.5 py-1 text-xs font-medium ${STATUS_TONE[status].tint}`}
    >
      {STATUS_LABELS[status]}
    </span>
  );
}

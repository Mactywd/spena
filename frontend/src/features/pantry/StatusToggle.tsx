import { STATUS_LABELS, STATUS_TONE } from "./statusLabels";
import type { PantryStatus } from "../../domain/types";

const OPTIONS: [PantryStatus, string][] = [
  ["available", STATUS_LABELS.available],
  ["low", STATUS_LABELS.low],
  ["finished", STATUS_LABELS.finished],
];

// Il controllo attraverso cui l'utente alimenta l'unico giudizio vero del sistema:
// "low" è quello che fa funzionare la regola primario/secondario delle ricette.
// Tre posizioni sempre visibili, bersagli da pollice: niente menu nascosto, niente
// tooltip — da telefono il passaggio del mouse non esiste.
//
// Il colore arriva da STATUS_TONE e non da qui: il foglio di cottura mostra gli
// stessi tre stati, e due schermi che se li colorano da soli prima o poi si
// contraddicono su quale sia il giallo di «quasi finito».
export function StatusToggle({
  value,
  onChange,
  disabled = false,
}: {
  value: PantryStatus;
  onChange: (status: PantryStatus) => void;
  disabled?: boolean;
}) {
  return (
    <div className="flex gap-1.5" role="group">
      {OPTIONS.map(([status, label]) => (
        <button
          key={status}
          type="button"
          // finché la modifica precedente è in volo: due PATCH sulla stessa voce
          // arrivano in ordine ignoto e l'ultima a rispondere vince
          disabled={disabled}
          onClick={() => onChange(status)}
          aria-pressed={value === status}
          className={`min-h-11 flex-1 rounded-full px-3 py-2 text-xs font-medium transition-colors disabled:opacity-50 ${
            value === status
              ? STATUS_TONE[status].fill
              : "bg-page text-ink-soft ring-1 ring-line ring-inset"
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

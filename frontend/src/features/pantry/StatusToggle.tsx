import type { PantryStatus } from "../../domain/types";

const OPTIONS: [PantryStatus, string][] = [
  ["available", "Disponibile"],
  ["low", "Quasi finito"],
  ["finished", "Finito"],
];

// Il controllo attraverso cui l'utente alimenta l'unico giudizio vero del sistema:
// "low" è quello che fa funzionare la regola primario/secondario delle ricette.
// Tre posizioni sempre visibili, bersagli da pollice: niente menu nascosto, niente
// tooltip — da telefono il passaggio del mouse non esiste.
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
    <div className="flex gap-1" role="group">
      {OPTIONS.map(([status, label]) => (
        <button
          key={status}
          type="button"
          // finché la modifica precedente è in volo: due PATCH sulla stessa voce
          // arrivano in ordine ignoto e l'ultima a rispondere vince
          disabled={disabled}
          onClick={() => onChange(status)}
          aria-pressed={value === status}
          className={`min-h-11 flex-1 rounded-full px-3 py-2 text-xs font-medium disabled:opacity-50 ${
            value === status ? "bg-emerald-700 text-white" : "bg-neutral-100 text-neutral-600"
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

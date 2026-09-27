import { useId, useState, type ReactNode } from "react";
import { Alert } from "../../components/ui/Alert";
import { buttonClasses } from "../../components/ui/buttonClasses";

/** Un campo modificabile in loco, con il suo «Salva» (spec §6.4).
 *
 * Un «Salva» per campo e non uno per la scheda: il nome, la marca e il codice sono tre
 * correzioni indipendenti, e un rifiuto su una non deve trattenere le altre. Se il
 * salvataggio fallisce il campo resta com'era scritto, e l'errore accanto (spec §7):
 * `describeError` lo dice a modo suo quando il rifiuto ha un'uscita da offrire.
 *
 * `required` (F17): quando il campo non può restare vuoto in colonna — il nome del
 * prodotto, non la marca — «Salva» resta spento a bozza vuota e il motivo si legge
 * sotto, come CustomProductForm e RenameForm già fanno: un pulsante spento e muto non
 * si spiega da sé.
 *
 * L'errore si cancella anche battendo un tasto, non solo quando il valore salvato
 * cambia da fuori: `describeError` (ProductScreen la usa per il rifiuto del codice)
 * riceve la bozza *attuale*, e le sue uscite (le due uscite del rifiuto §7, «Sposta il
 * codice qui» e «Usalo lo stesso») agiscono su quel che le arriva. Senza cancellare
 * l'errore a ogni battuta, un rifiuto rimasto a video dopo che si è scritto un codice
 * diverso mostrerebbe ancora le sue uscite, che manderebbero il codice nuovo — mai
 * confermato — come se fosse quello rifiutato (rilievo della revisione finale S9). */
export function InlineField({
  label,
  value,
  placeholder,
  inputMode,
  required = false,
  onSave,
  describeError,
}: {
  label: string;
  value: string;
  placeholder?: string;
  inputMode?: "text" | "numeric";
  required?: boolean;
  onSave: (next: string) => Promise<unknown>;
  describeError?: (error: unknown, draft: string) => ReactNode;
}) {
  const inputId = useId();
  const [draft, setDraft] = useState(value);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);

  // Il valore salvato cambia da fuori — la scheda riletta dopo un salvataggio, o dopo
  // «Sposta il codice qui» — e il campo lo riprende, perdendo l'errore vecchio. Durante
  // il disegno e non in un effetto, come in PantryRow: un effetto mostrerebbe per un
  // disegno il valore vecchio.
  const [seen, setSeen] = useState(value);
  if (value !== seen) {
    setSeen(value);
    setDraft(value);
    setError(null);
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      await onSave(draft.trim());
    } catch (caught) {
      setError(caught);
    } finally {
      setSaving(false);
    }
  }

  const trimmed = draft.trim();
  const changed = trimmed !== value;
  // (F17) un pulsante spento e muto non si spiega da sé: il motivo va scritto sotto
  const missing = required && trimmed === "";

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={inputId} className="text-sm font-medium text-ink-soft">
        {label}
      </label>
      <div className="flex items-center gap-2">
        <input
          id={inputId}
          value={draft}
          placeholder={placeholder}
          inputMode={inputMode}
          disabled={saving}
          onChange={(event) => {
            setDraft(event.target.value);
            setError(null);
          }}
          className="min-w-0 flex-1"
        />
        <button
          type="button"
          aria-label={`Salva ${label.toLowerCase()}`}
          disabled={!changed || saving || missing}
          onClick={() => void save()}
          className={`${buttonClasses("secondary")} shrink-0`}
        >
          Salva
        </button>
      </div>
      {missing && (
        <p className="text-xs text-ink-soft">Il campo «{label}» non può restare vuoto.</p>
      )}
      {error !== null &&
        (describeError ? (
          describeError(error, trimmed)
        ) : (
          <Alert>Non sono riuscito a salvare. Quel che hai scritto è ancora qui: riprova.</Alert>
        ))}
    </div>
  );
}

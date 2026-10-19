import { useId, useRef, useState, type ReactNode } from "react";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";

/** Un campo modificabile in loco, con il suo «Salva» (spec §6.4).
 *
 * Un «Salva» per campo e non uno per la scheda: il nome, la marca e il codice sono tre
 * correzioni indipendenti, e un rifiuto su una non deve trattenere le altre. Se il
 * salvataggio fallisce il campo resta com'era scritto, e l'errore accanto (spec §7):
 * `describeError` lo dice a modo suo quando il rifiuto ha un'uscita da offrire.
 *
 * «Salva» segue la regola dei pulsanti (pulizie del 2026-10-13): in volo è `busy`; a
 * campo obbligatorio vuoto è «non ancora», col perché scritto sotto (`required`, F17: un
 * pulsante spento e muto non si spiega da sé); invariato è `disabled`, lo stato di ogni
 * campo a riposo, dove non c'è niente da spiegare. Un `disabled` toglie il fuoco a chi ce
 * l'ha: per questo, dopo un salvataggio riuscito, il fuoco torna nel campo prima che
 * «Salva» si spenga.
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
  const inputRef = useRef<HTMLInputElement>(null);
  const saveRef = useRef<HTMLButtonElement>(null);
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
      // Riuscito: il valore salvato diventa quello scritto, e «Salva» sta per spegnersi
      // perché invariato. In volo era `busy` (il fuoco restava); spento con `disabled` lo
      // perderebbe, e chi usa la tastiera lo ritrovava sulla pagina. Se il fuoco era qui,
      // torna nel campo appena salvato prima che `saving` si spenga.
      if (document.activeElement === saveRef.current) inputRef.current?.focus();
    } catch (caught) {
      setError(caught);
    } finally {
      setSaving(false);
    }
  }

  const trimmed = draft.trim();
  const changed = trimmed !== value;
  const missing = required && trimmed === "";

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={inputId} className="text-sm font-medium text-ink-soft">
        {label}
      </label>
      {/* `flex-wrap` e `[&>p]:basis-full`: il perché di «Salva» è un `<p>` fratello del
          pulsante, che `Button` disegna sotto di sé, e va a capo sotto la riga invece di
          stringere il campo — come nello stepper delle porzioni */}
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 [&>p]:basis-full">
        <input
          id={inputId}
          ref={inputRef}
          value={draft}
          placeholder={placeholder}
          inputMode={inputMode}
          // in volo `readOnly` e non `disabled`: un campo che diventa `disabled` perde il fuoco
          readOnly={saving}
          onChange={(event) => {
            setDraft(event.target.value);
            setError(null);
          }}
          className="min-w-0 flex-1"
        />
        {/* `busy` e `unavailableReason` vincono su `disabled` (Button): in volo e a campo
            vuoto il fuoco resta qui */}
        <Button
          ref={saveRef}
          accessibleName={`Salva ${label.toLowerCase()}`}
          busy={saving}
          disabled={!changed}
          unavailableReason={missing ? `Il campo «${label}» non può restare vuoto.` : undefined}
          onClick={() => void save()}
          className="shrink-0"
        >
          Salva
        </Button>
      </div>
      {error !== null &&
        (describeError ? (
          describeError(error, trimmed)
        ) : (
          <Alert>Non sono riuscito a salvare. Quel che hai scritto è ancora qui: riprova.</Alert>
        ))}
    </div>
  );
}

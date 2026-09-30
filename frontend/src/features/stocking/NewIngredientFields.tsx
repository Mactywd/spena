import { useId, useState, type FormEvent } from "react";
import { Button } from "../../components/ui/Button";
import { CategorySelect } from "../../components/CategorySelect";

/** Il passo che crea un ingrediente nuovo: come si chiama in generale, e in che
 * reparto (spec T3 §4.3). Il nome parte da quel che gli si dà — il testo della voce —
 * ma è un campo da correggere: dal giro, «zucchine tonde di Nizza della signora Pina»
 * diventava il nome dell'ingrediente, e con lui ogni ricerca e ogni ricetta.
 *
 * Solo i campi: la creazione la fa chi lo usa, perché «Sistema la spesa» chiama
 * `POST /ingredients` e il modulo della ricetta (R12, Consegna 6) manda nome e reparto
 * dentro la ricetta. Sta in un file suo per quello.
 *
 * Il reparto non si indovina: si chiede. Parte da «altro», che è dove finiva d'ufficio:
 * chi non ha niente da dire fa esattamente quello che faceva prima. */
export function NewIngredientFields({
  initialName,
  busy,
  onSubmit,
  onCancel,
  foodOnly = false,
  submitLabel = "Crea l'ingrediente",
}: {
  initialName: string;
  /** Mentre la creazione è in volo: il pulsante si spegne ma tiene il fuoco. */
  busy: boolean;
  onSubmit: (fields: { name: string; category: string }) => void;
  onCancel: () => void;
  /** Solo i reparti del cibo: lo chiede il modulo della ricetta (R12), dove un non
   * alimentare verrebbe rifiutato al salvataggio. */
  foodOnly?: boolean;
  /** Il pulsante che conferma: «Crea l'ingrediente» in «Sistema la spesa», che lo crea
   * subito; «Aggiungi alla ricetta» nel modulo, dove nasce salvando la ricetta. */
  submitLabel?: string;
}) {
  const nameId = useId();
  const hintId = useId();
  const [name, setName] = useState(initialName);
  const [category, setCategory] = useState<string>("altro");
  const trimmed = name.trim();

  function submit(event: FormEvent) {
    event.preventDefault();
    // l'Invio nel campo invia il modulo anche col pulsante spento: la guardia sta qui
    if (trimmed === "" || busy) return;
    onSubmit({ name: trimmed, category });
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      <div className="flex flex-col gap-1.5">
        <label htmlFor={nameId} className="text-sm font-medium">
          Come si chiama in generale?
        </label>
        <input
          id={nameId}
          autoFocus
          value={name}
          onChange={(e) => setName(e.target.value)}
          aria-describedby={hintId}
        />
        <p id={hintId} className="text-xs text-ink-soft">
          Il nome che scriveresti in lista: «zucchine», non «zucchine tonde di Nizza».
        </p>
      </div>
      <CategorySelect value={category} onChange={setCategory} foodOnly={foodOnly} />
      <div>
        {/* `busy` in volo, `unavailableReason` a nome vuoto (Consegna 6a): il fuoco resta
            qui invece di cadere sul `body`, e il perché lo scrive Button sotto di sé */}
        <Button
          type="submit"
          variant="primary"
          shape="block"
          busy={busy}
          unavailableReason={trimmed === "" ? "Scrivi il nome per crearlo." : undefined}
        >
          {submitLabel}
        </Button>
      </div>
      <Button variant="ghost" onClick={onCancel} className="self-start">
        Annulla
      </Button>
    </form>
  );
}

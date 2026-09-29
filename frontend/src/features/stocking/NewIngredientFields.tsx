import { useId, useState, type FormEvent } from "react";
import { Button } from "../../components/ui/Button";
import { buttonClasses } from "../../components/ui/buttonClasses";
import { FOOD_CATEGORIES, NON_FOOD_CATEGORIES } from "../../domain/categories";

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
}: {
  initialName: string;
  /** Mentre la creazione è in volo: il pulsante si spegne ma tiene il fuoco. */
  busy: boolean;
  onSubmit: (fields: { name: string; category: string }) => void;
  onCancel: () => void;
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
      <label className="text-sm">
        Reparto
        <select
          aria-label="Reparto"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="mt-1.5"
        >
          {FOOD_CATEGORIES.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
          {/* staccati, perché sono un'altra cosa: non è un reparto in più del
              supermercato, è la metà dell'anagrafica che le ricette non vedono */}
          <optgroup label="Non alimentari">
            {NON_FOOD_CATEGORIES.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </optgroup>
        </select>
      </label>
      <div>
        {/* `aria-disabled` e non `disabled`: mentre la creazione è in volo il fuoco
            resta qui invece di cadere sul `body` */}
        <button
          type="submit"
          aria-disabled={busy || trimmed === "" || undefined}
          className={`${buttonClasses("primary", "block")} aria-disabled:opacity-40`}
        >
          Crea l'ingrediente
        </button>
        {/* un pulsante spento e muto non si spiega da sé */}
        {trimmed === "" && (
          <p className="pt-2 text-xs text-ink-soft">Scrivi il nome per crearlo.</p>
        )}
      </div>
      <Button variant="ghost" onClick={onCancel} className="self-start">
        Annulla
      </Button>
    </form>
  );
}

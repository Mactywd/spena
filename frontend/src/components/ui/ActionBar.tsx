import { useId, type FormEvent } from "react";
import { Button } from "./Button";
import { IconPlus, type IconComponent } from "./icons";

/** La barra in cima a Lista e Dispensa: il campo e il + accanto (spec T3 §2). Il
 * segnaposto del campo fa da etichetta visiva al +, che è di sola icona e porta il
 * suo nome completo per chi non vede. Il valore lo tiene chi la usa: in Dispensa lo
 * stesso testo filtra le righe mentre si scrive. */
export function ActionBar({
  inputLabel,
  placeholder,
  addLabel,
  value,
  onChange,
  onAdd,
  leadingIcon: Leading,
}: {
  inputLabel: string;
  placeholder: string;
  addLabel: string;
  value: string;
  onChange: (value: string) => void;
  onAdd: (text: string) => void;
  leadingIcon?: IconComponent;
}) {
  const id = useId();
  function submit(event: FormEvent) {
    event.preventDefault();
    const text = value.trim();
    if (text) onAdd(text);
  }
  return (
    <form onSubmit={submit} className="flex items-center gap-2">
      <div className="relative min-w-0 flex-1">
        {Leading && (
          <Leading
            aria-hidden="true"
            className="pointer-events-none absolute top-1/2 left-3 size-5 -translate-y-1/2 text-ink-faint"
          />
        )}
        <input
          id={id}
          aria-label={inputLabel}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className={`text-base ${Leading ? "pl-10" : ""}`}
        />
      </div>
      <Button type="submit" variant="primary" icon={IconPlus} label={addLabel} className="rounded-[10px]" />
    </form>
  );
}

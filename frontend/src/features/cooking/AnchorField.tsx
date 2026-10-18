import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { readAmount } from "./anchorAmount";

/** «Quanto ne fai?», sotto una riga d'ingrediente del dettaglio (R2, secondo modo).
 *
 * Il campo legge un numero e basta: il fattore, le dosi delle altre righe, le porzioni
 * equivalenti e il limite delle 50 volte li decide il server, che risponde a `onSubmit`.
 * Si riscala al tocco di «Riscala» o all'Invio, non a ogni cifra: ogni cifra sarebbe una
 * rilettura della ricetta, e le dosi salterebbero mentre si scrive.
 *
 * `onSubmit` torna `null` se la vista è cambiata — allora chi ha aperto il campo lo chiude
 * e questo componente si smonta — oppure la frase da mostrare sotto la casella, che resta
 * aperta col numero scritto: la strada per correggerlo (mai un vicolo cieco).
 *
 * L'etichetta è «Quanto ne fai?» con l'unità accanto alla casella, e non «Quanti g ne
 * fai?»: con l'unità dentro la domanda l'accordo dipende dall'unità («Quanti fette»), e il
 * registro delle unità non sa il genere (deciso da Mattia il 2026-10-13, spec §4). */
export function AnchorField({
  unit,
  initial,
  onSubmit,
  onCancel,
}: {
  /** La parola dell'unità della riga, accanto alla casella; `null` per un numero nudo. */
  unit: string | null;
  /** Il testo con cui si apre: vuoto, o la dose già fissata su questa riga. */
  initial: string;
  onSubmit: (amount: string) => Promise<string | null>;
  onCancel: () => void;
}) {
  const [text, setText] = useState(initial);
  const [pending, setPending] = useState(false);
  const [refusal, setRefusal] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const inputId = useId();
  const unitId = useId();

  // il campo si apre per essere scritto: il fuoco ci va da sé, e al telefono la tastiera
  // dei numeri si apre senza un secondo tocco
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const reading = readAmount(text);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (reading.amount === undefined || pending) return;
    setPending(true);
    setRefusal(null);
    const problem = await onSubmit(reading.amount);
    if (problem !== null) {
      setRefusal(problem);
      setPending(false);
    }
  }

  return (
    // `[&>p]`: il perché di «Riscala» (un `<p>` fratello disegnato da `Button`) e il
    // rifiuto del server vanno a capo in fondo, sotto tutta la riga, invece di stringersi
    // fra i due pulsanti
    <form
      onSubmit={(event) => void submit(event)}
      className="flex flex-wrap items-center gap-2 pt-2 [&>p]:order-last [&>p]:basis-full"
    >
      <label htmlFor={inputId} className="text-sm text-ink-soft">
        Quanto ne fai?
      </label>
      <input
        ref={inputRef}
        id={inputId}
        value={text}
        onChange={(event) => {
          setText(event.target.value);
          setRefusal(null);
        }}
        inputMode="decimal"
        autoComplete="off"
        enterKeyHint="done"
        aria-describedby={unit !== null ? unitId : undefined}
        className="min-h-11 w-28 text-right"
      />
      {unit !== null && (
        <span id={unitId} className="text-sm text-ink-soft">
          {unit}
        </span>
      )}
      <Button type="submit" busy={pending} unavailableReason={reading.problem}>
        Riscala
      </Button>
      <Button variant="ghost" onClick={onCancel}>
        Annulla
      </Button>
      {refusal !== null && <Alert>{refusal}</Alert>}
    </form>
  );
}

import { useId, useRef } from "react";
import { Button } from "../../components/ui/Button";
import { IconCopy } from "../../components/ui/icons";
import { useNotice } from "../../components/ui/noticeContext";

/** Un testo da portare in un'altra app (l'indirizzo, la chiave, le intestazioni di HC
 * Webhook): un campo di sola lettura e «Copia».
 *
 * Se gli appunti non ci sono (fuori da HTTPS) o il telefono rifiuta, il testo si seleziona
 * e l'avviso dice di copiarlo a mano tenendoci il dito sopra: mai un vicolo cieco. Niente
 * `document.execCommand("copy")`, deprecato. Il campo non ha `text-sm`: sotto i 16 px iOS
 * ingrandisce la pagina quando prende il fuoco. */
export function CopyField({ label, value }: { label: string; value: string }) {
  const id = useId();
  const input = useRef<HTMLInputElement>(null);
  const notify = useNotice();

  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      notify({ text: "Copiato." });
    } catch {
      input.current?.focus();
      input.current?.select();
      notify({ text: "Non riesco a copiare: tieni premuto sul testo e copialo a mano." });
    }
  }

  return (
    <div className="flex w-full flex-col gap-1">
      <label htmlFor={id} className="text-sm text-ink-soft">
        {label}
      </label>
      <div className="flex items-center gap-2">
        <input
          id={id}
          ref={input}
          readOnly
          value={value}
          spellCheck={false}
          autoCapitalize="none"
          autoCorrect="off"
          onFocus={(event) => event.currentTarget.select()}
          className="min-w-0 flex-1 font-mono"
        />
        <Button icon={IconCopy} accessibleName={`Copia: ${label}`} onClick={() => void copy()} className="shrink-0">
          Copia
        </Button>
      </div>
    </div>
  );
}

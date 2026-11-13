import { useId, type FormEvent } from "react";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import type { ChatMessage, RecipeChange } from "../../domain/types";

/** La risposta di Claude mentre arriva: il testo dei `delta` e le modifiche già fatte. */
export type StreamingReply = { text: string; changes: RecipeChange[] };

/** La riga di una modifica sotto la risposta. Le parole, «annullata» e «Annulla»
 * vengono da quello che dice il server: qui non si decide niente. */
function ChangeLine({
  change,
  onUndo,
  busy,
}: {
  change: RecipeChange;
  onUndo?: (changeId: string) => void;
  busy: boolean;
}) {
  const lineId = useId();
  const verb = change.created_recipe ? "Ricetta scritta" : "Ricetta aggiornata";
  return (
    <div className="flex flex-wrap items-center gap-x-2">
      <p id={lineId} className="min-w-0 py-1 text-sm break-words text-ink-soft">
        {`${verb}: ${change.summary}${change.undone ? " — annullata" : ""}`}
      </p>
      {onUndo && change.undoable && (
        <Button
          variant="ghost"
          className="-mx-2"
          busy={busy}
          aria-describedby={lineId}
          onClick={() => onUndo(change.id)}
        >
          Annulla
        </Button>
      )}
    </div>
  );
}

const BUBBLE = "max-w-[85%] rounded-card px-3 py-2 whitespace-pre-wrap break-words text-ink";

/** I fumetti di una chat con Claude: Mattia a destra, Claude a sinistra, sotto ogni
 * risposta le sue modifiche, sotto un messaggio non risposto il suo avviso e «Riprova».
 * Lo usa la chat del piatto e, domani, quella della pianificazione. */
export function ChatThread({
  messages,
  streaming,
  onUndo,
  onRetry,
  busy = false,
}: {
  messages: ChatMessage[];
  /** La risposta che sta arrivando, `null` se Claude non sta scrivendo. */
  streaming: StreamingReply | null;
  onUndo: (changeId: string) => void;
  onRetry: (message: ChatMessage) => void;
  /** Una richiesta della chat è in volo: «Annulla» e «Riprova» aspettano. */
  busy?: boolean;
}) {
  return (
    <div>
      <ol className="flex flex-col gap-2">
        {messages.map((message) => {
          const mine = message.role === "user";
          return (
            <li key={message.id} className={`flex flex-col ${mine ? "items-end" : "items-start"}`}>
              <p className={`${BUBBLE} ${mine ? "bg-brand-tint" : "bg-card"}`}>{message.text}</p>
              {message.changes.map((change) => (
                <ChangeLine key={change.id} change={change} onUndo={onUndo} busy={busy} />
              ))}
              {message.status === "failed" && (
                <div className="flex max-w-full flex-col items-end">
                  {message.notice && (
                    <Alert tone="degraded" className="pt-1 text-right">
                      {message.notice}
                    </Alert>
                  )}
                  <Button variant="ghost" className="-mx-2" busy={busy} onClick={() => onRetry(message)}>
                    Riprova
                  </Button>
                </div>
              )}
            </li>
          );
        })}
        {streaming && (streaming.text !== "" || streaming.changes.length > 0) && (
          <li className="flex flex-col items-start">
            {streaming.text !== "" && <p className={`${BUBBLE} bg-card`}>{streaming.text}</p>}
            {streaming.changes.map((change) => (
              // durante la risposta la riga c'è già, «Annulla» arriva con la risposta intera
              <ChangeLine key={change.id} change={change} busy={busy} />
            ))}
          </li>
        )}
      </ol>
      <p aria-live="polite" className="pt-1 text-sm text-ink-faint">
        {streaming ? "Claude sta scrivendo…" : ""}
      </p>
    </div>
  );
}

/** Il campo per scrivere a Claude. Invio va a capo: si manda solo con «Invia». */
export function ChatComposer({
  value,
  onChange,
  onSubmit,
  replying,
}: {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  /** Claude sta rispondendo: non si manda un secondo messaggio. */
  replying: boolean;
}) {
  const empty = value.trim() === "";
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!empty && !replying) onSubmit();
  }
  return (
    <form onSubmit={submit} className="flex flex-col items-end gap-2 pt-2">
      <textarea
        aria-label="Messaggio per Claude"
        placeholder="Scrivi a Claude…"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        rows={3}
        // il limite di `ChatMessageIn` nel backend: oltre, il server risponderebbe 422
        maxLength={4000}
      />
      <Button type="submit" variant="primary" busy={replying} disabled={empty}>
        Invia
      </Button>
    </form>
  );
}

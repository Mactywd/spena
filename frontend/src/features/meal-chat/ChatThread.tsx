import { useId, type FormEvent, type ReactNode } from "react";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import type { ChangeCard, ChatMessage, MealProposal, RecipeChange } from "../../domain/types";

/** La risposta di Claude mentre arriva: il testo dei `delta`, le modifiche già fatte e,
 * nella pianificazione, le proposte e le schede appena nate. */
export type StreamingReply = {
  text: string;
  changes: RecipeChange[];
  proposals?: MealProposal[];
  cards?: ChangeCard[];
};

/** La risposta che arriva vista come un messaggio, per chi rende le schede sotto di lei:
 * l'id non è di nessun messaggio salvato. */
function streamingMessage(reply: StreamingReply): ChatMessage {
  return {
    id: "streaming",
    role: "assistant",
    text: reply.text,
    status: "pending",
    notice: null,
    created_at: "",
    changes: reply.changes,
    proposals: reply.proposals ?? [],
    cards: reply.cards ?? [],
  };
}

/** Quello che `renderExtras` rende sotto un messaggio, in una colonna a tutta larghezza;
 * niente, se non rende niente. */
function Extras({ children }: { children: ReactNode }) {
  if (children === null || children === undefined || children === false) return null;
  return <div className="flex w-full flex-col gap-2 pt-1">{children}</div>;
}

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
 * Lo usano la chat del piatto e quella della pianificazione; `renderExtras` mette sotto
 * ogni messaggio (e sotto la risposta che arriva) quello che la chat ci vuole, come le
 * proposte e le schede dei cambi. */
export function ChatThread({
  messages,
  streaming,
  onUndo,
  onRetry,
  busy = false,
  renderExtras,
}: {
  messages: ChatMessage[];
  /** La risposta che sta arrivando, `null` se Claude non sta scrivendo. */
  streaming: StreamingReply | null;
  onUndo: (changeId: string) => void;
  onRetry: (message: ChatMessage) => void;
  /** Una richiesta della chat è in volo: «Annulla» e «Riprova» aspettano. */
  busy?: boolean;
  /** Quello che sta sotto un messaggio, dopo le sue modifiche; `null` per niente. */
  renderExtras?: (message: ChatMessage) => ReactNode;
}) {
  const live = streaming ? streamingMessage(streaming) : null;
  const liveExtras = live && renderExtras ? renderExtras(live) : null;
  return (
    <div>
      <ol className="flex flex-col gap-2">
        {messages.map((message) => {
          const mine = message.role === "user";
          return (
            <li key={message.id} className={`flex flex-col ${mine ? "items-end" : "items-start"}`}>
              {message.text !== "" && (
                <p className={`${BUBBLE} ${mine ? "bg-brand-tint" : "bg-card"}`}>{message.text}</p>
              )}
              {message.changes.map((change) => (
                <ChangeLine key={change.id} change={change} onUndo={onUndo} busy={busy} />
              ))}
              {renderExtras && <Extras>{renderExtras(message)}</Extras>}
              {message.status === "sent" && message.notice && (
                // una risposta fermata a metà (troppi passaggi): il testo c'è, l'avviso lo spiega, niente «Riprova»
                <Alert tone="degraded" className={`max-w-full pt-1 ${mine ? "text-right" : ""}`}>
                  {message.notice}
                </Alert>
              )}
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
        {streaming && (streaming.text !== "" || streaming.changes.length > 0 || liveExtras) && (
          <li className="flex flex-col items-start">
            {streaming.text !== "" && <p className={`${BUBBLE} bg-card`}>{streaming.text}</p>}
            {streaming.changes.map((change) => (
              // durante la risposta la riga c'è già, «Annulla» arriva con la risposta intera
              <ChangeLine key={change.id} change={change} busy={busy} />
            ))}
            <Extras>{liveExtras}</Extras>
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
      <Button
        type="submit"
        variant="primary"
        busy={replying}
        unavailableReason={empty ? "Scrivi prima il messaggio." : undefined}
      >
        Invia
      </Button>
    </form>
  );
}

import { useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ApiError } from "../../api/client";
import type { ChatMessage, ChatStreamEvent, RecipeChange } from "../../domain/types";
import type { StreamingReply } from "./ChatThread";

/** La frase di riserva quando un rifiuto non porta la sua (la rete, per esempio). */
const FALLBACK = "Non sono riuscito a farlo. Riprova fra poco.";

/** Un rifiuto della chat, con il suo tono: il guasto di Claude ha l'ambra di ogni guasto
 * dell'AI (`degraded`), «sta già rispondendo» è una nota, il resto un errore. */
export type Refusal = { text: string; tone: "error" | "note" | "degraded" };

export function refusalOf(error: unknown): Refusal {
  if (!(error instanceof ApiError)) return { text: FALLBACK, tone: "error" };
  const code = (error.body as { code?: unknown } | null)?.code;
  const tone = code === "claude_not_configured" ? "degraded" : code === "claude_busy" ? "note" : "error";
  return { text: error.message || FALLBACK, tone };
}

/** Il rifiuto da disegnare: nullo se dice quello che la schermata già dice in testa (Claude
 * non è collegato: l'avviso della vista e il 503 dell'invio hanno lo stesso testo). */
export function shownRefusal(
  refusal: Refusal | null,
  chat: { claude_ready: boolean; claude_notice: string | null } | undefined
): Refusal | null {
  if (refusal === null) return null;
  if (chat && !chat.claude_ready && chat.claude_notice && chat.claude_notice === refusal.text) return null;
  return refusal;
}

export type ChatBody = { text: string; retry_of?: string };

/** Il messaggio in volo: il fumetto di Mattia (da `start`) e la risposta che arriva. */
type Turn = { retryOf: string | null; user: ChatMessage | null; reply: StreamingReply };

const EMPTY_REPLY: StreamingReply = { text: "", changes: [], proposals: [], cards: [] };

/** La logica d'invio di una chat con Claude, una copia sola per il piatto e per la
 * pianificazione: il campo, il giro in volo, il rifiuto prima dello stream (il testo torna
 * nel campo), «Riprova» con `retry_of`, la vista in cache su `done` ed `error`, e la
 * rilettura quando lo stream finisce senza nessuno dei due. Chi la usa dice come si manda
 * (`send`), dove va la vista (`settle`) e come si rilegge (`refetch`). */
export function useChatSender<TChat>({
  send,
  settle,
  refetch,
  onChange,
}: {
  send: (body: ChatBody, onEvent: (event: ChatStreamEvent<TChat>) => void) => Promise<void>;
  settle: (chat: TChat) => void;
  refetch: () => void;
  /** Una modifica della ricetta appena fatta (la chat del piatto rilegge la ricetta). */
  onChange?: (change: RecipeChange) => void;
}) {
  const [draft, setDraft] = useState("");
  const [turn, setTurn] = useState<Turn | null>(null);
  const [refusal, setRefusal] = useState<Refusal | null>(null);
  // un giro alla volta: lo stato di React arriva tardi per due invii ravvicinati
  const inFlight = useRef(false);
  // i testi che non vengono dal campo arrivati durante un giro (il seguito di «Metti nella
  // settimana» toccato mentre Claude scrive): partono da soli quando il giro finisce
  const queued = useRef<string[]>([]);

  // Una mutazione e non una chiamata nuda: un 401 riporta all'accesso come ogni altra
  // scrittura (la `MutationCache` dell'app).
  const mutation = useMutation({
    mutationFn: ({ body, onEvent }: { body: ChatBody; onEvent: (event: ChatStreamEvent<TChat>) => void }) =>
      send(body, onEvent),
  });

  /** `fromField`: il testo viene dal campo, che si svuota; se il messaggio non parte torna
   * nel campo, se intanto non se n'è scritto un altro. Un testo che non viene dal campo (il
   * seguito di «Metti nella settimana») non tocca il campo: se un giro è in volo aspetta che
   * finisca e parte da solo; se il messaggio non parte, entra nel campo — vuoto, da solo;
   * con un testo scritto da Mattia, dopo quel testo, che resta com'è. Mai perso. */
  async function submit(text: string, retryOf: string | null, fromField: boolean) {
    if (inFlight.current) {
      if (!fromField && retryOf === null) queued.current.push(text);
      return;
    }
    inFlight.current = true;
    setRefusal(null);
    if (fromField) setDraft("");
    setTurn({ retryOf, user: null, reply: EMPTY_REPLY });
    let started = false;
    let ended = false;
    const onEvent = (event: ChatStreamEvent<TChat>) => {
      switch (event.name) {
        case "start":
          started = true;
          setTurn((t) => (t ? { ...t, user: event.message } : t));
          break;
        case "delta":
          setTurn((t) => (t ? { ...t, reply: { ...t.reply, text: t.reply.text + event.text } } : t));
          break;
        case "change":
          setTurn((t) =>
            t ? { ...t, reply: { ...t.reply, changes: [...t.reply.changes, event.change] } } : t
          );
          onChange?.(event.change);
          break;
        case "proposal":
          setTurn((t) =>
            t
              ? { ...t, reply: { ...t.reply, proposals: [...(t.reply.proposals ?? []), event.proposal] } }
              : t
          );
          break;
        case "card":
          setTurn((t) =>
            t ? { ...t, reply: { ...t.reply, cards: [...(t.reply.cards ?? []), event.card] } } : t
          );
          break;
        case "done":
          ended = true;
          settle(event.chat);
          break;
        case "error":
          // Senza la chat (il server non l'ha potuta rileggere) non si scrive null nella
          // cache: `ended` resta falso e il `finally` la rilegge.
          if (event.chat !== null) {
            ended = true;
            settle(event.chat);
          }
          break;
      }
    };
    try {
      await mutation.mutateAsync({ body: retryOf ? { text, retry_of: retryOf } : { text }, onEvent });
    } catch (error) {
      // Rifiutato prima dello stream: il messaggio non è partito, il testo torna nel campo.
      // Rotto a metà: il messaggio è salvato, e lo dice la rilettura qui sotto.
      if (!started) {
        setRefusal(refusalOf(error));
        if (fromField) setDraft((current) => (current === "" ? text : current));
        else if (retryOf === null)
          setDraft((current) =>
            current === "" ? text : current.includes(text) ? current : `${current}\n\n${text}`
          );
      }
    } finally {
      // Senza `done` né `error` (il giro è caduto dopo aver salvato, o la connessione si è
      // rotta) la verità è sul server: si rilegge, e la lettura riprende a interrogare
      // finché Claude risponde. Mai «Claude sta scrivendo…» per sempre.
      if (!ended) refetch();
      setTurn(null);
      inFlight.current = false;
      const next = queued.current.shift();
      if (next !== undefined) void submit(next, null, false);
    }
  }

  /** Quello che il filo mostra, dalla chat letta e dal giro in volo. */
  function thread(data: { messages: ChatMessage[]; replying: boolean } | undefined) {
    const replying = turn !== null || data?.replying === true;
    // Il messaggio che si sta riprovando sparisce subito: il server lo toglie.
    const saved = (data?.messages ?? []).filter((m) => m.id !== turn?.retryOf);
    const shown =
      turn?.user && !saved.some((m) => m.id === turn.user?.id) ? [...saved, turn.user] : saved;
    const streaming: StreamingReply | null =
      turn !== null ? turn.reply : data?.replying ? EMPTY_REPLY : null;
    const empty = data !== undefined && shown.length === 0 && turn === null;
    return { replying, shown, streaming, empty };
  }

  return {
    draft,
    setDraft,
    refusal,
    setRefusal,
    /** Un giro è in volo da qui. */
    sending: turn !== null,
    /** Il messaggio scritto nel campo. */
    sendDraft: () => void submit(draft.trim(), null, true),
    /** Un messaggio che non viene dal campo. */
    sendText: (text: string) => void submit(text, null, false),
    retry: (message: ChatMessage) => void submit(message.text, message.id, false),
    thread,
  };
}

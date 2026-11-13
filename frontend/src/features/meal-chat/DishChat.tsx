import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ApiError } from "../../api/client";
import { Alert } from "../../components/ui/Alert";
import { SectionHeading } from "../../components/ui/SectionHeading";
import { useNotice } from "../../components/ui/noticeContext";
import type { ChatMessage, ChatStreamEvent, DishChat as DishChatData, Meal } from "../../domain/types";
import { MEALS_KEY } from "../meals/api";
import { dishChatKey, sendDishMessage, undoRecipeChange, useDishChat } from "./api";
import { ChatComposer, ChatThread, type StreamingReply } from "./ChatThread";

/** La frase di riserva quando un rifiuto non porta la sua (la rete, per esempio). */
const FALLBACK = "Non sono riuscito a farlo. Riprova fra poco.";

/** Il messaggio in volo: il fumetto di Mattia (da `start`) e la risposta che arriva. */
type Turn = { retryOf: string | null; user: ChatMessage | null; reply: StreamingReply };

/** Un rifiuto della chat, con il suo tono: il guasto di Claude ha l'ambra di ogni guasto
 * dell'AI (`degraded`), «sta già rispondendo» è una nota, il resto un errore. */
type Refusal = { text: string; tone: "error" | "note" | "degraded" };

function refusalOf(error: unknown): Refusal {
  if (!(error instanceof ApiError)) return { text: FALLBACK, tone: "error" };
  const code = (error.body as { code?: unknown } | null)?.code;
  const tone = code === "claude_not_configured" ? "degraded" : code === "claude_busy" ? "note" : "error";
  return { text: error.message || FALLBACK, tone };
}

/** La chat con Claude sotto la ricetta di un pasto (spec 2026-11-12 §5.3). */
export function DishChat({ mealId, hasRecipe }: { mealId: string; hasRecipe: boolean }) {
  const queryClient = useQueryClient();
  const notice = useNotice();
  const chat = useDishChat(mealId, true);
  const [draft, setDraft] = useState("");
  const [turn, setTurn] = useState<Turn | null>(null);
  const [refusal, setRefusal] = useState<Refusal | null>(null);

  /** La ricetta del pasto, con la chiave del dettaglio (`["recipe", id, …]`). Se il pasto
   * in cache non ne ha ancora una (Claude l'ha appena scritta), tutte: rilegge solo quella
   * a video. */
  function refreshRecipe() {
    const meal = queryClient.getQueryData<Meal>([...MEALS_KEY, "meal", mealId]);
    const recipeId = meal?.recipe?.id;
    void queryClient.invalidateQueries({ queryKey: recipeId ? ["recipe", recipeId] : ["recipe"] });
    void queryClient.invalidateQueries({ queryKey: MEALS_KEY });
  }

  function settle(next: DishChatData) {
    queryClient.setQueryData(dishChatKey(mealId), next);
    void queryClient.invalidateQueries({ queryKey: MEALS_KEY });
  }

  // Una mutazione e non una chiamata nuda: un 401 riporta all'accesso come ogni altra
  // scrittura (la `MutationCache` dell'app).
  const send = useMutation({
    mutationFn: ({ body, onEvent }: { body: { text: string; retry_of?: string }; onEvent: (event: ChatStreamEvent) => void }) =>
      sendDishMessage(mealId, body, onEvent),
  });

  const undo = useMutation({
    mutationFn: (changeId: string) => undoRecipeChange(mealId, changeId),
  });

  async function submit(text: string, retryOf: string | null) {
    setRefusal(null);
    if (retryOf === null) setDraft("");
    setTurn({ retryOf, user: null, reply: { text: "", changes: [] } });
    let started = false;
    let ended = false;
    const onEvent = (event: ChatStreamEvent) => {
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
          refreshRecipe();
          break;
        case "done":
        case "error":
          ended = true;
          settle(event.chat);
          break;
      }
    };
    try {
      await send.mutateAsync({ body: retryOf ? { text, retry_of: retryOf } : { text }, onEvent });
    } catch (error) {
      // Rifiutato prima dello stream: il messaggio non è partito, il testo torna nel campo
      // (se intanto non se n'è scritto un altro). Rotto a metà: il messaggio è salvato, e
      // lo dice la rilettura qui sotto.
      if (!started) {
        setRefusal(refusalOf(error));
        if (retryOf === null) setDraft((current) => (current === "" ? text : current));
      }
    } finally {
      // Senza `done` né `error` (il giro è caduto dopo aver salvato, o la connessione si è
      // rotta) la verità è sul server: si rilegge, e la lettura riprende a interrogare
      // finché Claude risponde. Mai «Claude sta scrivendo…» per sempre.
      if (!ended) void queryClient.invalidateQueries({ queryKey: dishChatKey(mealId) });
      setTurn(null);
    }
  }

  function retry(message: ChatMessage) {
    void submit(message.text, message.id);
  }

  function undoChange(changeId: string) {
    setRefusal(null);
    undo.mutate(changeId, {
      onSuccess: (next) => {
        queryClient.setQueryData(dishChatKey(mealId), next);
        refreshRecipe();
        notice({ text: "Modifica annullata." });
      },
      onError: (error) => setRefusal(refusalOf(error)),
    });
  }

  const data = chat.data;
  const replying = turn !== null || data?.replying === true;
  // Il messaggio che si sta riprovando sparisce subito: il server lo toglie.
  const saved = (data?.messages ?? []).filter((m) => m.id !== turn?.retryOf);
  const shown =
    turn?.user && !saved.some((m) => m.id === turn.user?.id) ? [...saved, turn.user] : saved;
  const streaming: StreamingReply | null =
    turn !== null ? turn.reply : data?.replying ? { text: "", changes: [] } : null;
  const empty = data !== undefined && shown.length === 0 && turn === null;

  return (
    <section>
      <SectionHeading>Chat con Claude</SectionHeading>
      <div className="flex flex-col gap-2">
        {data && !data.claude_ready && data.claude_notice && (
          <Alert tone="degraded">{data.claude_notice}</Alert>
        )}
        {empty && (
          <p className="text-sm text-ink-soft">
            {hasRecipe
              ? "Chiedi a Claude di cambiare la ricetta: la vedi aggiornata qui sopra."
              : "Chiedi a Claude di scrivere la ricetta di questo piatto."}
          </p>
        )}
        <ChatThread
          messages={shown}
          streaming={streaming}
          onUndo={undoChange}
          onRetry={retry}
          busy={replying || undo.isPending}
        />
        {refusal && <Alert tone={refusal.tone}>{refusal.text}</Alert>}
        <ChatComposer
          value={draft}
          onChange={setDraft}
          onSubmit={() => void submit(draft.trim(), null)}
          replying={replying}
        />
      </div>
    </section>
  );
}

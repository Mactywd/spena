import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Alert } from "../../components/ui/Alert";
import { SectionHeading } from "../../components/ui/SectionHeading";
import { useNotice } from "../../components/ui/noticeContext";
import type { ChatMessage, DishChat as DishChatData, Meal } from "../../domain/types";
import { ChangeCard } from "../change-cards/ChangeCard";
import { MEALS_KEY } from "../meals/api";
import { dishChatKey, sendDishMessage, undoRecipeChange, useDishChat } from "./api";
import { CONTINUE_TEXT, ChatComposer, ChatThread } from "./ChatThread";
import { refusalOf, shownRefusal, useChatSender } from "./useChatSender";

/** La chat con Claude sotto la ricetta di un pasto (spec 2026-11-12 §5.3). */
export function DishChat({ mealId, hasRecipe }: { mealId: string; hasRecipe: boolean }) {
  const queryClient = useQueryClient();
  const notice = useNotice();
  const chat = useDishChat(mealId, true);

  /** La ricetta del pasto, con la chiave del dettaglio (`["recipe", id, …]`). Se il pasto
   * in cache non ne ha ancora una (Claude l'ha appena scritta), tutte: rilegge solo quella
   * a video. */
  function refreshRecipe() {
    const meal = queryClient.getQueryData<Meal>([...MEALS_KEY, "meal", mealId]);
    const recipeId = meal?.recipe?.id;
    void queryClient.invalidateQueries({ queryKey: recipeId ? ["recipe", recipeId] : ["recipe"] });
    void queryClient.invalidateQueries({ queryKey: MEALS_KEY });
  }

  const sender = useChatSender<DishChatData>({
    send: (body, onEvent) => sendDishMessage(mealId, body, onEvent),
    settle: (next) => {
      queryClient.setQueryData(dishChatKey(mealId), next);
      void queryClient.invalidateQueries({ queryKey: MEALS_KEY });
    },
    refetch: () => void queryClient.invalidateQueries({ queryKey: dishChatKey(mealId) }),
    onChange: refreshRecipe,
  });
  const { draft, setDraft, setRefusal } = sender;

  const undo = useMutation({
    mutationFn: (changeId: string) => undoRecipeChange(mealId, changeId),
  });

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

  /** Le schede dei cambi di un messaggio, sotto il fumetto (anche quella che arriva in diretta). */
  function extras(message: ChatMessage) {
    const cards = message.cards ?? [];
    if (cards.length === 0) return null;
    return (
      <>
        {cards.map((c) => (
          <ChangeCard key={c.id} card={c} />
        ))}
      </>
    );
  }

  const data = chat.data;
  const refusal = shownRefusal(sender.refusal, data);
  const { replying, shown, streaming, empty } = sender.thread(data);

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
          onRetry={sender.retry}
          onContinue={() => sender.sendText(CONTINUE_TEXT)}
          busy={replying || undo.isPending}
          renderExtras={extras}
        />
        {refusal && <Alert tone={refusal.tone}>{refusal.text}</Alert>}
        <ChatComposer
          value={draft}
          onChange={setDraft}
          onSubmit={sender.sendDraft}
          replying={replying}
        />
      </div>
    </section>
  );
}

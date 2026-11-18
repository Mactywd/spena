import { useQuery } from "@tanstack/react-query";
import { apiFetch, apiStream } from "../../api/client";
import type { ChatStreamEvent, DishChat } from "../../domain/types";
import { readSse } from "./sse";

/** Tutte le chat dei piatti in cache. */
export const DISH_CHATS_KEY = ["meal-chat"] as const;

/** La chat di un pasto in cache. */
export function dishChatKey(mealId: string) {
  return [...DISH_CHATS_KEY, mealId] as const;
}

export function fetchDishChat(mealId: string) {
  return apiFetch<DishChat>(`/meals/${mealId}/chat`);
}

/** Manda un messaggio e legge la risposta di Claude evento per evento. Un rifiuto prima
 * dello stream (503, 409, 422…) arriva come `ApiError`, e allora nessun evento è passato. */
export async function sendDishMessage(
  mealId: string,
  body: { text: string; retry_of?: string },
  onEvent: (event: ChatStreamEvent) => void
): Promise<void> {
  const response = await apiStream(`/meals/${mealId}/chat/messages`, {
    method: "POST",
    headers: { Accept: "text/event-stream" },
    body: JSON.stringify(body),
  });
  await readSse(response, onEvent);
}

export function undoRecipeChange(mealId: string, changeId: string) {
  return apiFetch<DishChat>(`/meals/${mealId}/chat/changes/${changeId}/undo`, { method: "POST" });
}

/** La chat del piatto. Mentre il server dice che Claude sta rispondendo (per esempio
 * riaprendo il piatto a metà risposta), si rilegge ogni due secondi. */
export function useDishChat(mealId: string, enabled: boolean) {
  return useQuery({
    queryKey: dishChatKey(mealId),
    queryFn: () => fetchDishChat(mealId),
    enabled,
    refetchInterval: (query) => (query.state.data?.replying ? 2000 : false),
  });
}

import type { QueryClient } from "@tanstack/react-query";
import { apiFetch, apiStream } from "../../api/client";
import type { ChatStreamEvent, MealSlot, PlaceResult, PlanningChat } from "../../domain/types";
import { readSse } from "../meal-chat/sse";
import type { ChatBody } from "../meal-chat/useChatSender";

/** Tutto ciò che riguarda la pianificazione in cache. */
export const PLANNING_KEY = ["planning"] as const;

/** Una conversazione di pianificazione in cache. */
export function planningChatKey(conversationId: string) {
  return [...PLANNING_KEY, "conversation", conversationId] as const;
}

export type Focus = { day: string; slot: MealSlot };

/** L'ultima conversazione non conclusa, o la vista vuota (`conversation_id` null). */
export function fetchCurrentPlanning() {
  return apiFetch<PlanningChat>("/planning/current");
}

export function fetchPlanning(id: string) {
  return apiFetch<PlanningChat>(`/planning/conversations/${id}`);
}

/** «Nuova», anche con il posto di partenza. */
export function createPlanning(focus?: Focus) {
  return apiFetch<PlanningChat>("/planning/conversations", {
    method: "POST",
    body: JSON.stringify({ focus: focus ?? null }),
  });
}

/** Il posto di partenza, cambiato o tolto (`null`). */
export function setPlanningFocus(id: string, focus: Focus | null) {
  return apiFetch<PlanningChat>(`/planning/conversations/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ focus }),
  });
}

/** Manda un messaggio e legge la risposta di Claude evento per evento, come nel piatto.
 * Un rifiuto prima dello stream (503, 409, 422…) arriva come `ApiError`. */
export async function sendPlanningMessage(
  id: string,
  body: ChatBody,
  onEvent: (event: ChatStreamEvent<PlanningChat>) => void
): Promise<void> {
  const response = await apiStream(`/planning/conversations/${id}/messages`, {
    method: "POST",
    headers: { Accept: "text/event-stream" },
    body: JSON.stringify(body),
  });
  await readSse<PlanningChat>(response, onEvent);
}

/** «Metti nella settimana»; `replace` è la conferma per i posti occupati. */
export function placeProposal(id: string, replace: boolean): Promise<PlaceResult> {
  return apiFetch<PlaceResult>(`/planning/proposals/${id}/place`, {
    method: "POST",
    body: JSON.stringify({ replace }),
  });
}

/** Una vista della chat arrivata dal server, nella cache della sua conversazione. */
export function putPlanningChat(queryClient: QueryClient, chat: PlanningChat) {
  if (chat.conversation_id !== null) {
    queryClient.setQueryData(planningChatKey(chat.conversation_id), chat);
  }
}

import { useEffect, useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ApiError } from "../../api/client";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { Chip } from "../../components/ui/Chip";
import { ErrorState } from "../../components/ui/ErrorState";
import { IconX } from "../../components/ui/icons";
import { Screen } from "../../components/ui/Screen";
import type { ChatMessage, MealSlot, PlanningChat } from "../../domain/types";
import { ChangeCard } from "../change-cards/ChangeCard";
import { ChatComposer, ChatThread } from "../meal-chat/ChatThread";
import { refusalOf, useChatSender } from "../meal-chat/useChatSender";
import { SLOT_LABELS, longDayLabel } from "../meals/format";
import {
  PLANNING_KEY,
  createPlanning,
  fetchCurrentPlanning,
  fetchPlanning,
  planningChatKey,
  putPlanningChat,
  sendPlanningMessage,
  setPlanningFocus,
  type Focus,
} from "./api";
import { ProposalCard } from "./ProposalCard";

const DAY = /^\d{4}-\d{2}-\d{2}$/;
const CURRENT_KEY = [...PLANNING_KEY, "current"] as const;
const HERE = "/pasti/pianifica";

const at = (conversationId: string) => `${HERE}?conversazione=${conversationId}`;

/** La domanda già scritta nel campo quando si arriva da un posto vuoto (decisione 25). */
function focusQuestion(focus: Focus): string {
  return `Cosa mi proponi per ${longDayLabel(focus.day)} a ${SLOT_LABELS[focus.slot].toLowerCase()}?`;
}

/** «Pianifica con Claude» (spec 2026-11-12 §5.2): la chat a tutta pagina, con le proposte
 * e le schede dei cambi sotto i messaggi. Si apre su `?conversazione=<id>`, altrimenti
 * sull'ultima conversazione non conclusa (la sceglie il server); con `?giorno&posto` la
 * conversazione si punta su quel posto. Il primo messaggio senza conversazione la crea. */
export function PlanningScreen() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const conversationId = params.get("conversazione");
  const focusDay = params.get("giorno");
  const focusSlotParam = params.get("posto");
  const focusSlot: MealSlot | null =
    focusSlotParam === "lunch" || focusSlotParam === "dinner" ? focusSlotParam : null;
  const wantsFocus = focusDay !== null && DAY.test(focusDay) && focusSlot !== null;

  const chat = useQuery({
    queryKey: conversationId ? planningChatKey(conversationId) : CURRENT_KEY,
    queryFn: () => (conversationId ? fetchPlanning(conversationId) : fetchCurrentPlanning()),
    // mentre si punta il posto, la conversazione arriva da lì
    enabled: !wantsFocus,
    // mentre il server dice che Claude sta rispondendo (riaprendo a metà risposta), si rilegge
    refetchInterval: (query) => (query.state.data?.replying ? 2000 : false),
  });

  const sender = useChatSender<PlanningChat>({
    send: async (body, onEvent) => {
      let id = conversationId ?? chat.data?.conversation_id ?? null;
      if (id === null) {
        // il primo messaggio apre la conversazione
        const created = await createPlanning();
        putPlanningChat(queryClient, created);
        id = created.conversation_id as string;
        navigate(at(id), { replace: true });
      }
      await sendPlanningMessage(id, body, onEvent);
    },
    settle: (next) => putPlanningChat(queryClient, next),
    refetch: () => void queryClient.invalidateQueries({ queryKey: PLANNING_KEY }),
  });
  const { setDraft, setRefusal } = sender;

  const create = useMutation({ mutationFn: (focus?: Focus) => createPlanning(focus) });
  const focus = useMutation({
    mutationFn: ({ id, focus }: { id: string; focus: Focus | null }) => setPlanningFocus(id, focus),
  });
  const createAsync = create.mutateAsync;
  const focusAsync = focus.mutateAsync;

  // Da un posto vuoto: la conversazione aperta si punta lì, o se ne crea una col posto.
  // Una volta sola per indirizzo, anche se l'effetto ripassa.
  const focusDone = useRef<string | null>(null);
  useEffect(() => {
    if (!wantsFocus || focusDay === null || focusSlot === null) return;
    const wanted: Focus = { day: focusDay, slot: focusSlot };
    const marker = `${conversationId ?? ""}|${wanted.day}|${wanted.slot}`;
    if (focusDone.current === marker) return;
    focusDone.current = marker;
    void (async () => {
      try {
        const target =
          conversationId ??
          (await queryClient.fetchQuery({ queryKey: CURRENT_KEY, queryFn: fetchCurrentPlanning }))
            .conversation_id;
        const next = target
          ? await focusAsync({ id: target, focus: wanted })
          : await createAsync(wanted);
        putPlanningChat(queryClient, next);
        setDraft(focusQuestion(wanted));
        navigate(at(next.conversation_id as string), { replace: true });
      } catch (error) {
        // il posto non si è fissato: la domanda resta nel campo, la chat si apre lo stesso
        setRefusal(refusalOf(error));
        setDraft(focusQuestion(wanted));
        navigate(conversationId ? at(conversationId) : HERE, { replace: true });
      }
    })();
  }, [
    wantsFocus, focusDay, focusSlot, conversationId, queryClient, navigate, focusAsync, createAsync,
    setDraft, setRefusal,
  ]);

  // L'ultima conversazione aperta, letta senza id: l'indirizzo passa a lei, così ogni
  // scrittura dopo ha una cache sola, quella della conversazione.
  const currentId = conversationId === null ? chat.data?.conversation_id ?? null : null;
  useEffect(() => {
    if (currentId === null || chat.data === undefined) return;
    putPlanningChat(queryClient, chat.data);
    navigate(at(currentId), { replace: true });
  }, [currentId, chat.data, queryClient, navigate]);

  // Una conversazione che non c'è più: si riparte dall'ultima aperta, mai un vicolo cieco.
  const gone = chat.error instanceof ApiError && chat.error.status === 404;
  useEffect(() => {
    if (gone) navigate(HERE, { replace: true });
  }, [gone, navigate]);

  function startNew() {
    setRefusal(null);
    create.mutate(undefined, {
      onSuccess: (next) => {
        putPlanningChat(queryClient, next);
        setDraft("");
        navigate(at(next.conversation_id as string), { replace: true });
      },
      onError: (error) => setRefusal(refusalOf(error)),
    });
  }

  function clearFocus(id: string) {
    setRefusal(null);
    focus.mutate(
      { id, focus: null },
      {
        onSuccess: (next) => putPlanningChat(queryClient, next),
        onError: (error) => setRefusal(refusalOf(error)),
      }
    );
  }

  function extras(message: ChatMessage) {
    const proposals = message.proposals ?? [];
    const cards = message.cards ?? [];
    if (proposals.length === 0 && cards.length === 0) return null;
    return (
      <>
        {proposals.map((p) => (
          // il seguito della messa parte subito, come un messaggio qualsiasi
          <ProposalCard key={p.id} proposal={p} onPlaced={sender.sendText} />
        ))}
        {cards.map((c) => (
          <ChangeCard key={c.id} card={c} />
        ))}
      </>
    );
  }

  const data = chat.data;
  const { replying, shown, streaming, empty } = sender.thread(data);

  return (
    <Screen
      title="Pianifica con Claude"
      back={{ to: "/pasti", label: "Pasti" }}
      action={
        // una colonna: il perché di «non ancora» sta sotto il pulsante
        <div className="flex flex-col items-end">
          <Button
            variant="ghost"
            busy={create.isPending}
            // mentre la risposta arriva, una conversazione nuova la coprirebbe
            unavailableReason={sender.sending ? "Aspetta che Claude finisca di rispondere." : undefined}
            onClick={startNew}
          >
            Nuova
          </Button>
        </div>
      }
    >
      <div className="flex flex-col gap-2">
        {data && !data.claude_ready && data.claude_notice && (
          <Alert tone="degraded">{data.claude_notice}</Alert>
        )}
        {chat.isError && !gone ? (
          <ErrorState
            message="La conversazione non si carica."
            onRetry={() => chat.refetch()}
            retrying={chat.isFetching}
          />
        ) : !data ? (
          <p className="text-sm text-ink-soft">Carico la conversazione…</p>
        ) : (
          <>
            {data.focus && data.conversation_id && (
              <div className="flex items-center gap-1">
                <Chip tone="bg-brand-tint text-ink">
                  {`Per: ${longDayLabel(data.focus.day)} · ${SLOT_LABELS[data.focus.slot]}`}
                </Chip>
                <Button
                  variant="ghost"
                  icon={IconX}
                  label="Togli il posto"
                  busy={focus.isPending}
                  onClick={() => clearFocus(data.conversation_id as string)}
                />
              </div>
            )}
            {empty && (
              <p className="text-sm text-ink-soft">
                Dimmi come vuoi pianificare: con quello che c'è in casa, o una bozza prima della spesa.
              </p>
            )}
            <ChatThread
              messages={shown}
              streaming={streaming}
              // la pianificazione non scrive ricette: nessuna modifica da annullare
              onUndo={() => {}}
              onRetry={sender.retry}
              busy={replying}
              renderExtras={extras}
            />
          </>
        )}
        {sender.refusal && <Alert tone={sender.refusal.tone}>{sender.refusal.text}</Alert>}
        {data && (
          <ChatComposer
            value={sender.draft}
            onChange={setDraft}
            onSubmit={sender.sendDraft}
            replying={replying}
          />
        )}
      </div>
    </Screen>
  );
}

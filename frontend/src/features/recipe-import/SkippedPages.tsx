import { useId, useState } from "react";
import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { ApiError } from "../../api/client";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { buttonClasses } from "../../components/ui/buttonClasses";
import { IconChevronDown, IconChevronRight } from "../../components/ui/icons";
import { useNotice } from "../../components/ui/noticeContext";
import type { SkippedPage } from "../../domain/types";
import { fetchSkippedPages, requeuePage, SKIPPED_PAGES_KEY } from "./api";
import {
  cookingWaitingText,
  requeueResultMessage,
  skipReasonText,
  skippedTitle,
} from "./skippedWords";

/** Un 4xx porta nel `detail` il perché vero («non è più scartata», «non aveva una ricetta
 * leggibile»): si mostra com'è, come fa la coda con le decisioni. Un guasto no. */
function requeueErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.status >= 400 && error.status < 500) {
    return error.message;
  }
  return "Non sono riuscito a rimetterla in coda. Niente è andato perso: riprova.";
}

function SkippedPageRow({
  page,
  pending,
  onRequeue,
}: {
  page: SkippedPage;
  pending: boolean;
  onRequeue: () => void;
}) {
  // una pagina illeggibile non ha titolo: la si nomina col suo indirizzo
  const name = page.title ?? page.url;
  return (
    <li className="flex items-center justify-between gap-3 border-b border-line py-3 last:border-b-0">
      <div className="min-w-0">
        <p className="truncate font-medium">{name}</p>
        <p className="pt-0.5 text-xs text-ink-soft">
          {skipReasonText(page.cause, page.non_food_name)}
        </p>
        {page.waiting_cooking_events > 0 && (
          <p className="pt-0.5 text-xs text-ink-soft">
            {cookingWaitingText(page.waiting_cooking_events)}
          </p>
        )}
      </div>
      {page.requeueable ? (
        // il nome accessibile porta la pagina: una riga per pagina, e senza il nome chi
        // ascolta sente N «Rimetti in coda» indistinguibili
        <Button
          variant="ghost"
          busy={pending}
          onClick={onRequeue}
          accessibleName={`Rimetti in coda «${name}»`}
          className="shrink-0 whitespace-nowrap"
        >
          Rimetti in coda
        </Button>
      ) : (
        // spec §2: rimetterla non può riuscire, quindi la strada è la
        // pagina originale, da leggere sul sito e scrivere a mano
        <a
          href={page.url}
          target="_blank"
          rel="noreferrer"
          aria-label={`Apri la pagina «${name}»`}
          className={`${buttonClasses("ghost")} shrink-0 whitespace-nowrap`}
        >
          Apri la pagina
        </a>
      )}
    </li>
  );
}

/** Le pagine scaricate che non sono diventate ricette (spec 2026-10-09-scartate-in-coda).
 *
 * Chiusa di partenza: la coda resta la cosa da fare, e le scartate sono un'eccezione da
 * guardare quando serve. Il numero arriva dallo stato che la coda legge già; l'elenco si
 * chiede solo aprendo, 50 per volta. «Rimetti in coda» manda la pagina per la strada
 * normale e l'avviso dice com'è finita; la riga dice sempre la strada per correggere la
 * causa, perché resta anche quando l'avviso se n'è andato.
 */
export function SkippedPages({ count }: { count: number }) {
  const [open, setOpen] = useState(false);
  const [requeueError, setRequeueError] = useState<string | null>(null);
  const contentId = useId();
  const queryClient = useQueryClient();
  const notice = useNotice();
  const navigate = useNavigate();

  const list = useInfiniteQuery({
    queryKey: SKIPPED_PAGES_KEY,
    initialPageParam: 0,
    queryFn: ({ pageParam }) => fetchSkippedPages(pageParam),
    // da dove riparte la pagina dopo: quante ne sono arrivate, finché il totale non è
    // raggiunto; una pagina vuota chiude (l'elenco si è accorciato sotto di noi)
    getNextPageParam: (lastPage, allPages) => {
      const loaded = allPages.reduce((sum, page) => sum + page.pages.length, 0);
      return lastPage.pages.length > 0 && loaded < lastPage.total ? loaded : undefined;
    },
    enabled: open,
  });
  const pages = list.data?.pages.flatMap((page) => page.pages) ?? [];

  const requeue = useMutation({
    mutationFn: (pageId: string) => requeuePage(pageId),
    onMutate: () => setRequeueError(null),
    onSuccess: (result) => {
      const text = requeueResultMessage(result);
      const recipeId = result.outcome === "imported" ? result.recipe_id : null;
      notice(
        recipeId !== null
          ? { text, action: { label: "Apri", onClick: () => navigate(`/ricette/${recipeId}`) } }
          : { text }
      );
      // `["import-status"]` è anche il prefisso di questo elenco (vedi SKIPPED_PAGES_KEY):
      // si rileggono il numero e le righe insieme. La coda e il ricettario sono cambiati
      // anche loro: un termine può essere tornato in attesa, una ricetta è entrata.
      queryClient.invalidateQueries({ queryKey: ["import-status"] });
      queryClient.invalidateQueries({ queryKey: ["import-terms"] });
      queryClient.invalidateQueries({ queryKey: ["recipes"] });
    },
    onError: (error) => {
      setRequeueError(requeueErrorMessage(error));
      // Un 409 dice che la pagina non è più scartata: l'elenco era vecchio. Lo si rilegge
      // (insieme al numero, sotto lo stesso prefisso), così il messaggio è vero e la riga
      // stantia se ne va. Un guasto (5xx, rete) no: rileggere a ogni errore girerebbe a vuoto.
      if (error instanceof ApiError && error.status === 409) {
        queryClient.invalidateQueries({ queryKey: ["import-status"] });
      }
    },
  });

  if (count === 0) return null;

  const Chevron = open ? IconChevronDown : IconChevronRight;
  return (
    <section aria-label={skippedTitle(count)} className="pt-6">
      {/* tutto il titolo è il pulsante, dentro l'`h2` (lo schema ARIA dell'accordion, come
          i reparti di S15); mai spento, quindi un `<button>` scritto a mano */}
      <h2 className="text-sm font-medium text-ink-soft">
        <button
          type="button"
          aria-expanded={open}
          aria-controls={contentId}
          onClick={() => setOpen((value) => !value)}
          className="flex min-h-11 w-full items-center gap-2 text-left"
        >
          <Chevron aria-hidden="true" className="size-4 shrink-0 text-ink-faint" stroke={1.8} />
          {skippedTitle(count)}
        </button>
      </h2>
      <div id={contentId} hidden={!open}>
        <p className="text-xs text-ink-faint">
          Le pagine scaricate che non sono diventate ricette, ciascuna col suo perché.
          Rimessa in coda, una pagina entra nel ricettario se la causa è stata corretta; se
          no torna qui.
        </p>
        {requeueError && <Alert className="pt-2">{requeueError}</Alert>}
        {open && list.isPending && (
          <p className="pt-2 text-sm text-ink-soft">Carico le pagine scartate…</p>
        )}
        {list.isError && (
          <div className="flex flex-wrap items-center gap-2 pt-2">
            <Alert>Non sono riuscito a leggere le pagine scartate.</Alert>
            <Button busy={list.isFetching} onClick={() => void list.refetch()}>
              Riprova
            </Button>
          </div>
        )}
        {pages.length > 0 && (
          <ul className="pt-2">
            {pages.map((page) => (
              <SkippedPageRow
                key={page.id}
                page={page}
                pending={requeue.isPending}
                onRequeue={() => requeue.mutate(page.id)}
              />
            ))}
          </ul>
        )}
        {list.hasNextPage && (
          <Button
            busy={list.isFetchingNextPage}
            onClick={() => void list.fetchNextPage()}
            className="mt-2"
          >
            Mostra altre
          </Button>
        )}
      </div>
    </section>
  );
}

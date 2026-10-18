import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query";
import { UnauthorizedError } from "../api/client";
import { defaultQueryRetryPredicate } from "./queryRetry";

/** Il client react-query dell'app. Uno solo, per `App.tsx` e — con i tentativi senza
 * attesa — per i test (`src/test/queryClient.ts`): un test che si costruisce il suo client
 * prova quello e non questo, e un client che ritentava per sempre è passato così sotto
 * ogni test di schermata (prima lezione di CLAUDE.md).
 *
 * Un 401 da qualsiasi chiamata riporta all'accesso, senza schermate rotte. Servono
 * entrambe le cache: le query leggono, ma spuntare una voce, cambiare uno stato in
 * dispensa e cucinare una ricetta sono mutazioni, e una sessione scaduta a metà di una di
 * quelle lascerebbe la schermata ferma su dati vecchi senza dire perché. */
export function createAppQueryClient(onUnauthorized: () => void): QueryClient {
  const bounceToLogin = (error: unknown) => {
    if (error instanceof UnauthorizedError) onUnauthorized();
  };
  return new QueryClient({
    queryCache: new QueryCache({ onError: bounceToLogin }),
    mutationCache: new MutationCache({ onError: bounceToLogin }),
    defaultOptions: {
      queries: {
        retry: defaultQueryRetryPredicate,
      },
    },
  });
}

import type { QueryClient } from "@tanstack/react-query";
import { createAppQueryClient } from "../lib/queryClient";

/** Il client dei test di schermata: quello dell'app (`createAppQueryClient`), col suo
 * predicato di retry e le sue due cache, con una sola differenza — i tentativi non
 * aspettano (`retryDelay: 0`). I tentativi sono quelli veri: un guasto si vede dopo il
 * terzo, come in produzione; l'attesa vera fra l'uno e l'altro (1 s, 2 s) renderebbe ogni
 * ramo d'errore lungo tre secondi. Nessun test se ne costruisce uno a mano
 * (`noLocalQueryClient.test.ts`). */
export function createTestQueryClient(onUnauthorized: () => void = () => {}): QueryClient {
  const client = createAppQueryClient(onUnauthorized);
  const defaults = client.getDefaultOptions();
  client.setDefaultOptions({ ...defaults, queries: { ...defaults.queries, retryDelay: 0 } });
  return client;
}

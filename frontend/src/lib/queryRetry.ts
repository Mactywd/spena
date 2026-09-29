import { ApiError } from "../api/client";

// Due risposte non si ritentano. Un 401: la sessione è scaduta e il rimbalzo al login
// è già partito (`UnauthorizedError` è un `ApiError` con 401). Un 404: la cosa chiesta
// non c'è, e chiederla di nuovo non la fa comparire — ritentarlo teneva lo schermo su
// «Carico…» per tre secondi, per poi offrire un «Riprova» che non poteva riuscire
// (Parte X di docs/prossimi-passi.md). Tutto il resto si ritenta, ma un numero finito
// di volte: un predicato che ignora il conteggio ritenta per sempre, `isError` non
// diventa mai vero e ogni ramo d'errore dell'app resta irraggiungibile — lo schermo
// resta su "Carico…" senza dire niente, che è il vicolo cieco che le regole di casa
// vietano.
const NOT_RETRIED = new Set([401, 404]);

export const defaultQueryRetryPredicate = (count: number, error: unknown) =>
  count < 2 && !(error instanceof ApiError && NOT_RETRIED.has(error.status));

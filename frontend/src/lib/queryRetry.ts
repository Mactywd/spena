import { UnauthorizedError } from "../api/client";

// Un 401 non si ritenta: la sessione è scaduta e il rimbalzo al login è
// già partito. Tutto il resto si ritenta, ma un numero finito di volte:
// un predicato che ignora il conteggio ritenta per sempre, `isError` non
// diventa mai vero e ogni ramo d'errore dell'app resta irraggiungibile —
// lo schermo resta su "Carico…" senza dire niente, che è il vicolo cieco
// che le regole di casa vietano.
export const defaultQueryRetryPredicate = (count: number, error: unknown) =>
  count < 2 && !(error instanceof UnauthorizedError);

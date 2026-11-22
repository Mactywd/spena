import { ApiError } from "./client";

/** La frase da schermo di un guasto dell'AI, se il backend l'ha mandata.
 *
 * Il 503 di un guasto dell'AI porta `{"code": "llm_<tipo>", "detail": <frase>}`: la
 * frase è scritta una volta sola nel backend (`LLM_FAILURE_NOTICES`, spec llm-haiku §5)
 * e qui si legge e basta. Nessuna corrispondenza fra tipo e parole nel TypeScript:
 * senza frase (un 503 d'altra origine, un errore di rete) è `null`, e lo schermo dice
 * la sua frase generica. */
export function aiNoticeOf(error: unknown): string | null {
  if (!(error instanceof ApiError) || error.status !== 503) return null;
  const body = error.body;
  if (typeof body !== "object" || body === null) return null;
  const { code, detail } = body as { code?: unknown; detail?: unknown };
  if (typeof code !== "string" || !code.startsWith("llm_")) return null;
  if (typeof detail !== "string" || detail === "") return null;
  return detail;
}

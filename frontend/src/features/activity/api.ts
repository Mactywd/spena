import { apiFetch } from "../../api/client";
import type { Activity, NewToken } from "./types";

/** La rotta che HC Webhook chiama dal telefono (fuori dalla sessione, con la chiave). */
export const WEBHOOK_PATH = "/api/v1/activity/hc-webhook";

export function fetchActivity(): Promise<Activity> {
  return apiFetch<Activity>("/activity");
}

/** Crea la chiave, o la rigenera: quella di prima smette di valere. */
export function createToken(): Promise<NewToken> {
  return apiFetch<NewToken>("/activity/token", { method: "POST" });
}

/** L'indirizzo da incollare in HC Webhook: il dominio da cui si sta guardando Spena, che è
 * quello su cui il server risponde. Nessuna configurazione da tenere allineata. */
export function webhookUrl(origin: string = window.location.origin): string {
  return `${origin}${WEBHOOK_PATH}`;
}

/** Le intestazioni per «Gestisci intestazioni» › «JSON» di HC Webhook: un incolla solo. */
export function headersJson(token: NewToken): string {
  return JSON.stringify({ [token.header]: token.token });
}

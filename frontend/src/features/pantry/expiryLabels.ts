import type { ExpiryState } from "../../domain/types";

/** La data come si legge, e il tempo verbale che porta la differenza. Nessuna delle
 * due forme concorda in genere: la riga può chiamarsi «Fage Total 0%» o «passata di
 * pomodoro», e un participio ne sbaglierebbe sempre una. */
export function formatExpiry(expiresOn: string, expiry: ExpiryState | null): string {
  const quando = new Date(expiresOn).toLocaleDateString("it-IT");
  return expiry === "expired" ? `Scadeva il ${quando}` : `Scade il ${quando}`;
}

/** Tinta leggera mentre si avvicina, piena da scaduta. Sta qui e non accanto al
 * componente per la ragione scritta in statusLabels.ts: un export costante accanto a
 * un componente rompe il fast refresh. */
export const EXPIRY_TONE: Record<ExpiryState, string> = {
  soon: "bg-expiry-tint text-expiry",
  expired: "bg-expiry text-white",
};

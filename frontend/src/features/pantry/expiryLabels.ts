import type { ExpiryState } from "../../domain/types";

/** La data come si legge, e il tempo verbale che porta la differenza. Nessuna delle
 * due forme concorda in genere: la riga può chiamarsi «Fage Total 0%» o «passata di
 * pomodoro», e un participio ne sbaglierebbe sempre una.
 *
 * `expiresOn` è una data-senza-ora ("2026-09-28"): `new Date("2026-09-28")` la
 * leggerebbe come mezzanotte UTC, e in un fuso indietro rispetto a UTC quella
 * mezzanotte cade ancora nel giorno prima in ora locale — la pastiglia mostrerebbe
 * un giorno sbagliato in silenzio. Per questo i tre numeri si prendono dalla
 * stringa e si passano al costruttore posizionale di `Date`, che li legge in ora
 * locale: nessun giorno attraversa un fuso orario, come vuole `PANTRY_TZ` sul
 * backend. */
export function formatExpiry(expiresOn: string, expiry: ExpiryState | null): string {
  const [anno, mese, giorno] = expiresOn.split("-").map(Number);
  const data = new Date(anno, mese - 1, giorno);
  // il costruttore posizionale mappa gli anni 0-99 sul 1900-1999 («0002-10-15»
  // diventerebbe «15/10/1902»): `setFullYear` gli ridà l'anno che ha davvero.
  // Non tocca le date normali — un 2026 resta 2026 — e serve perché un anno a una
  // cifra è raggiungibile battendo a mano nel campo data, prima che sia finito.
  data.setFullYear(anno);
  const quando = data.toLocaleDateString("it-IT");
  return expiry === "expired" ? `Scadeva il ${quando}` : `Scade il ${quando}`;
}

/** Tinta leggera mentre si avvicina, piena da scaduta. Sta qui e non accanto al
 * componente per la ragione scritta in statusLabels.ts: un export costante accanto a
 * un componente rompe il fast refresh. */
export const EXPIRY_TONE: Record<ExpiryState, string> = {
  soon: "bg-expiry-tint text-expiry",
  expired: "bg-expiry text-white",
};

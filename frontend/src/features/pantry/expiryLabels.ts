import type { ExpiryState } from "../../domain/types";

/** Il `max` di ogni campo data della scadenza.
 *
 * Senza, Chromium lascia battere un anno di sei cifre («202026-09-28»), e il campo
 * lo consegna com'è. È lo stesso limite di `datetime.date.max` in Python — il
 * backend legge `expires_on` come `date`, e un anno oltre il 9999 non lo sa nemmeno
 * rappresentare — quindi il campo non può più produrre una data che il server
 * rifiuterebbe. Non è un limite di plausibilità (fra quanti anni scade un barattolo
 * non è una decisione da prendere qui) e non ha un gemello `min`: una data già
 * passata è legittima, la si scrive il giorno dopo col barattolo in mano (D5). */
export const EXPIRY_INPUT_MAX = "9999-12-31";

const DAY_MS = 86_400_000;

// La data-senza-ora letta in ora locale: `new Date("2026-09-28")` la leggerebbe come
// mezzanotte UTC, e in un fuso indietro rispetto a UTC quella mezzanotte cade ancora
// nel giorno prima in ora locale. Per questo i tre numeri si prendono dalla stringa
// e si passano al costruttore posizionale di `Date`, che li legge in ora locale —
// nessun giorno attraversa un fuso orario, come vuole `PANTRY_TZ` sul backend. Il
// costruttore posizionale mappa però gli anni 0-99 sul 1900-1999 («0002-10-15»
// diventerebbe l'anno 1902): `setFullYear` gli ridà l'anno che ha davvero, utile per
// un anno a una cifra raggiungibile battendo a mano nel campo data.
function localDate(expiresOn: string): Date {
  const [anno, mese, giorno] = expiresOn.split("-").map(Number);
  const data = new Date(anno, mese - 1, giorno);
  data.setFullYear(anno);
  return data;
}

// Giorni di calendario fra due date. Si contano sulle date UTC costruite con i
// numeri del calendario, non sui millisecondi locali: il giorno del cambio d'ora
// dura 23 o 25 ore, e una divisione per 24 sbaglierebbe di uno.
function daysBetween(from: Date, to: Date): number {
  const a = Date.UTC(from.getFullYear(), from.getMonth(), from.getDate());
  const b = Date.UTC(to.getFullYear(), to.getMonth(), to.getDate());
  return Math.round((b - a) / DAY_MS);
}

// «15 nov», e l'anno solo se non è quello di oggi (dal giro: le date avevano
// sempre l'anno, anche quando non diceva niente)
function shortDate(date: Date, today: Date): string {
  const options: Intl.DateTimeFormatOptions = { day: "numeric", month: "short" };
  if (date.getFullYear() !== today.getFullYear()) options.year = "numeric";
  return date.toLocaleDateString("it-IT", options);
}

/** La scadenza come si legge sulla riga (spec T3 §4.1): relativa quando il backend
 * dice che è vicina o passata da un giorno, assoluta altrimenti. Quale voce è «in
 * scadenza» lo decide `expiry`: qui non c'è nessuna soglia di giorni. «Scadeva» e
 * non «scaduto», per non sbagliare l'accordo col nome della voce. */
export function expiryText(expiresOn: string, expiry: ExpiryState | null, today: Date = new Date()): string {
  const date = localDate(expiresOn);
  const days = daysBetween(today, date);
  if (expiry === "soon") {
    if (days <= 0) return "scade oggi";
    if (days === 1) return "scade domani";
    return `scade tra ${days} gg`;
  }
  if (expiry === "expired") {
    if (days >= -1) return "scadeva ieri";
    return `scadeva il ${shortDate(date, today)}`;
  }
  return `scade il ${shortDate(date, today)}`;
}

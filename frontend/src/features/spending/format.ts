import type { DaySpend } from "./types";

// Le parole delle spese dell'AI. Solo scrittura: le cifre, i giorni e le quote li decide
// il server.

// Dollari, perché è la valuta del listino di Anthropic: una conversione in euro sarebbe un
// cambio inventato. Il simbolo stretto («$» e non «USD»), dopo la cifra, come scrive
// l'italiano; fra i due uno spazio che non va a capo.
const CENTS = new Intl.NumberFormat("it-IT", {
  style: "currency",
  currency: "USD",
  currencyDisplay: "narrowSymbol",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});
// Sotto il dollaro le cifre vere sono frazioni di centesimo (una decisione dell'import
// costa ~0,0001 $): due decimali scriverebbero «0,00 $» per un mese di spesa vera.
const FRACTIONS = new Intl.NumberFormat("it-IT", {
  style: "currency",
  currency: "USD",
  currencyDisplay: "narrowSymbol",
  minimumFractionDigits: 2,
  maximumFractionDigits: 4,
});
const SMALLEST = 0.0001;

export function formatUsd(value: number): string {
  if (value <= 0) return CENTS.format(0);
  // sotto il decimillesimo «0,0000 $» direbbe zero, e zero non è
  if (value < SMALLEST) return `< ${FRACTIONS.format(SMALLEST)}`;
  return value < 1 ? FRACTIONS.format(value) : CENTS.format(value);
}

const PERCENT = new Intl.NumberFormat("it-IT", { style: "percent", maximumFractionDigits: 0 });

export function formatShare(share: number): string {
  // «0%» accanto a una barra che si vede direbbe il falso
  if (share > 0 && share < 0.005) return "< 1%";
  return PERCENT.format(share);
}

// Un giorno `AAAA-MM-GG` come data locale: la data è già quella di Roma, e costruirla dai
// numeri del calendario non la fa slittare col fuso di chi guarda.
function localDate(iso: string): Date {
  const [year, month, day] = iso.split("-").map(Number);
  return new Date(year, month - 1, day);
}

export function formatDay(iso: string): string {
  return localDate(iso).toLocaleDateString("it-IT", { day: "numeric", month: "long" });
}

export function formatDayShort(iso: string): string {
  return localDate(iso).toLocaleDateString("it-IT", { day: "numeric", month: "short" });
}

// «dall'1», «dall'8», «dall'11»: davanti a un numero che si legge con una vocale
const VOWEL_DAYS = new Set([1, 8, 11]);
const from = (day: number) => (VOWEL_DAYS.has(day) ? `dall'${day}` : `dal ${day}`);
const to = (day: number) => (VOWEL_DAYS.has(day) ? `all'${day}` : `al ${day}`);
const monthName = (date: Date) => date.toLocaleDateString("it-IT", { month: "long" });

/** Il periodo in parole: «13 ottobre», «dall'1 al 13 ottobre», «dal 14 settembre al 13
 * ottobre»; l'anno solo quando cambia. */
export function formatRange(first: string, last: string): string {
  if (first === last) return formatDay(first);
  const a = localDate(first);
  const b = localDate(last);
  if (a.getFullYear() !== b.getFullYear()) {
    return `${from(a.getDate())} ${monthName(a)} ${a.getFullYear()} ${to(b.getDate())} ${monthName(b)} ${b.getFullYear()}`;
  }
  if (a.getMonth() !== b.getMonth()) {
    return `${from(a.getDate())} ${monthName(a)} ${to(b.getDate())} ${monthName(b)}`;
  }
  return `${from(a.getDate())} ${to(b.getDate())} ${monthName(b)}`;
}

export function callsText(calls: number): string {
  return calls === 1 ? "1 chiamata" : `${calls} chiamate`;
}

/** «48.300»: il punto delle migliaia a mano, perché non dipenda dai dati ICU della macchina. */
export function formatTokens(tokens: number): string {
  return String(Math.round(tokens)).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

/** Le chiamate senza un costo (decisa da Mattia il 2026-10-13): il
 * totale non le comprende, e lo si dice invece di lasciarlo credere completo. */
export function unpricedText(unpriced: number): string {
  return unpriced === 1
    ? "1 senza un costo (di solito, una chiamata fallita): non è nel totale."
    : `${unpriced} senza un costo (di solito, chiamate fallite): non sono nel totale.`;
}

/** Il giorno più caro, che dà l'altezza alle colonne; il primo a parità. `null` se nessun
 * giorno ha una spesa. */
export function peakDay(days: DaySpend[]): DaySpend | null {
  let peak: DaySpend | null = null;
  for (const day of days) {
    if (day.cost_usd > 0 && (peak === null || day.cost_usd > peak.cost_usd)) peak = day;
  }
  return peak;
}

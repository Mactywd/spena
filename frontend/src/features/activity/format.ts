import type { ActivitySync, Connection, ExerciseSession } from "./types";

// I giorni arrivano già di Roma (`YYYY-MM-DD`): qui si scrivono e basta. In UTC, perché la
// data letta non scivoli al giorno prima nel fuso del telefono.
const WEEKDAY = new Intl.DateTimeFormat("it-IT", { weekday: "short", timeZone: "UTC" });
const MONTH_SHORT = new Intl.DateTimeFormat("it-IT", { month: "short", timeZone: "UTC" });
const MONTH_LONG = new Intl.DateTimeFormat("it-IT", { month: "long", timeZone: "UTC" });
const DAY_MS = 86_400_000;

function asDate(iso: string): Date {
  const [year, month, day] = iso.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day));
}

function daysBefore(day: string, today: string): number {
  return Math.round((asDate(today).getTime() - asDate(day).getTime()) / DAY_MS);
}

/** Il nome di un giorno in un elenco: «Oggi», «Ieri», «dom 11 ott». */
export function dayLabel(day: string, today: string): string {
  const before = daysBefore(day, today);
  if (before === 0) return "Oggi";
  if (before === 1) return "Ieri";
  const date = asDate(day);
  return `${WEEKDAY.format(date)} ${date.getUTCDate()} ${MONTH_SHORT.format(date)}`;
}

/** Un momento dentro una frase: «oggi alle 14:05», «ieri alle 23:50», «7 ottobre alle 09:10». */
export function momentText(day: string, time: string, today: string): string {
  const before = daysBefore(day, today);
  const date = asDate(day);
  const when =
    before === 0 ? "oggi" : before === 1 ? "ieri" : `${date.getUTCDate()} ${MONTH_LONG.format(date)}`;
  return `${when} alle ${time}`;
}

/** 8421 → «8.421». A mano e non con `Intl`: in italiano `Intl` non separa le migliaia sotto
 * le diecimila (misurato: «8421»), e in una colonna di passi «8421» sopra «12.345» non si
 * legge. */
export function formatSteps(steps: number): string {
  return String(steps).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

function decimal(value: number): string {
  return value.toFixed(1).replace(".", ",");
}

/** 72.4 → «72,4 kg». */
export function formatKg(kilograms: number): string {
  return `${decimal(kilograms)} kg`;
}

/** «Corsa · 32 min · 5,1 km», col titolo «Corsa («Giro del parco») · 32 min». */
export function exerciseLine(exercise: ExerciseSession): string {
  const name = exercise.title ? `${exercise.label} («${exercise.title}»)` : exercise.label;
  const parts = [name, `${exercise.minutes} min`];
  if (exercise.distance_km !== null) parts.push(`${decimal(exercise.distance_km)} km`);
  return parts.join(" · ");
}

/** La prima riga di «Attività». */
export function syncText(sync: ActivitySync, today: string): string {
  const moment = momentText(sync.day, sync.time, today);
  if (sync.status === "test") {
    return `Ultima sincronizzazione: ${moment}, la prova di HC Webhook: arrivata, e non salva niente.`;
  }
  if (sync.status === "rejected") return `Ultima sincronizzazione: ${moment}, rifiutata.`;
  return `Ultima sincronizzazione: ${moment}.`;
}

/** Lo stato della chiave, quando c'è. */
export function connectionText(connection: Connection, today: string): string {
  const created = `Chiave creata ${momentText(connection.created_day ?? today, connection.created_time ?? "", today)}.`;
  if (connection.last_used_day === null || connection.last_used_time === null) {
    return `${created} Non ancora usata.`;
  }
  return `${created} Usata l'ultima volta ${momentText(connection.last_used_day, connection.last_used_time, today)}.`;
}

/** I tipi arrivati che Spena non usa, e dove toglierli. */
export function ignoredText(labels: string[]): string {
  return `Arrivati e non usati: ${labels.join(", ")}. Nel webhook di Spena, in HC Webhook, si possono togliere.`;
}

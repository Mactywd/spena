import type { MealSlot } from "../../domain/types";

export const SLOT_LABELS: Record<MealSlot, string> = { lunch: "Pranzo", dinner: "Cena" };

// Solo forma: i giorni arrivano già decisi dal server. Si formatta in UTC su
// «<giorno>T00:00:00Z», così il giorno non scivola col fuso del telefono.
function parts(day: string, options: Intl.DateTimeFormatOptions) {
  return new Intl.DateTimeFormat("it-IT", { timeZone: "UTC", ...options }).format(
    new Date(`${day}T00:00:00Z`)
  );
}

function capitalize(text: string) {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** «Lunedì 10» */
export function dayLabel(day: string): string {
  return capitalize(parts(day, { weekday: "long", day: "numeric" }));
}

/** «martedì 11 novembre» */
export function longDayLabel(day: string): string {
  return parts(day, { weekday: "long", day: "numeric", month: "long" });
}

/** «10–16 novembre», «27 ottobre – 2 novembre», «29 dicembre 2025 – 4 gennaio 2026» */
export function weekLabel(monday: string, sunday: string): string {
  const [y1, m1] = monday.split("-");
  const [y2, m2] = sunday.split("-");
  if (y1 !== y2) {
    const full = { day: "numeric", month: "long", year: "numeric" } as const;
    return `${parts(monday, full)} – ${parts(sunday, full)}`;
  }
  if (m1 !== m2) {
    const short = { day: "numeric", month: "long" } as const;
    return `${parts(monday, short)} – ${parts(sunday, short)}`;
  }
  return `${parts(monday, { day: "numeric" })}–${parts(sunday, { day: "numeric", month: "long" })}`;
}

/** I segni di un pasto, come nella settimana e nella sua schermata: un solo segno dopo
 * «Fuori casa», «Non registrata» prima di «Bozza» (una bozza nel passato è quella non
 * registrata), poi «Avanzo». */
export function mealMarks(meal: {
  away: boolean;
  unrecorded: boolean;
  status: "draft" | "official";
  leftover_of: unknown;
}): string[] {
  const marks: string[] = [];
  if (meal.away) marks.push("Fuori casa");
  if (meal.unrecorded) marks.push("Non registrata");
  else if (meal.status === "draft") marks.push("Bozza");
  if (meal.leftover_of) marks.push("Avanzo");
  return marks;
}

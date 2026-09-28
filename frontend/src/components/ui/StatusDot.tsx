import type { Availability } from "../../domain/types";
import { STATUS_LABELS } from "../../features/pantry/statusLabels";

// I colori sono quelli degli stati della dispensa (STATUS_TONE): «manca» è il rosso di
// «finito», perché per una ricetta sono la stessa notizia. Le parole di «disponibile» e
// «quasi finito» si prendono da STATUS_LABELS e non si ribattono qui: un solo
// vocabolario per gli stessi stati, che non può scollarsi da quello della dispensa.
// «manca» resta sua: è la disponibilità di una ricetta, e in dispensa non esiste.
const DOT: Record<Availability, { colour: string; words: string }> = {
  available: { colour: "bg-brand", words: STATUS_LABELS.available.toLowerCase() },
  low: { colour: "bg-low", words: STATUS_LABELS.low.toLowerCase() },
  missing: { colour: "bg-finished", words: "manca" },
};

/** Il pallino accanto a un ingrediente di ricetta (spec T3 §4.6). Il colore da solo
 * non basta a chi non lo distingue: il pallino ha un nome, letto da chi ascolta. */
export function StatusDot({ availability }: { availability: Availability }) {
  const { colour, words } = DOT[availability];
  return <span role="img" aria-label={words} className={`inline-block size-2 shrink-0 rounded-full ${colour}`} />;
}

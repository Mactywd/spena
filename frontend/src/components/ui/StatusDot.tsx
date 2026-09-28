import type { Availability } from "../../domain/types";

// I colori sono quelli degli stati della dispensa (STATUS_TONE): «manca» è il rosso di
// «finito», perché per una ricetta sono la stessa notizia. Le parole sono quelle di
// STATUS_LABELS (ruling del controller): un solo vocabolario per gli stessi tre
// stati, non uno diverso qui e uno in dispensa.
const DOT: Record<Availability, { colour: string; words: string }> = {
  available: { colour: "bg-brand", words: "disponibile" },
  low: { colour: "bg-low", words: "quasi finito" },
  missing: { colour: "bg-finished", words: "manca" },
};

/** Il pallino accanto a un ingrediente di ricetta (spec T3 §4.6). Il colore da solo
 * non basta a chi non lo distingue: il pallino ha un nome, letto da chi ascolta. */
export function StatusDot({ availability }: { availability: Availability }) {
  const { colour, words } = DOT[availability];
  return <span role="img" aria-label={words} className={`inline-block size-2 shrink-0 rounded-full ${colour}`} />;
}

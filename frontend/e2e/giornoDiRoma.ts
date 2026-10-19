/** Il giorno di calendario a Roma fra `fraGiorni` giorni, come «AAAA-MM-GG».
 *
 * Il backend giudica le scadenze nel giorno di Europe/Rome (`PANTRY_TZ`), non in quello di
 * UTC: una data scritta da una prova deve essere quella che un utente a Roma vedrebbe sul
 * calendario. Si prende il giorno di Roma di `adesso` e ci si sommano giorni di calendario,
 * non 24 ore: la notte del cambio d'ora dura 23 o 25 ore, e il giorno dopo resta il giorno
 * dopo. */
export function giornoDiRoma(fraGiorni: number, adesso: Date = new Date()): string {
  // `en-CA` scrive le date come AAAA-MM-GG
  const oggi = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Europe/Rome",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(adesso);
  const [anno, mese, giorno] = oggi.split("-").map(Number);
  return new Date(Date.UTC(anno, mese - 1, giorno + fraGiorni)).toISOString().slice(0, 10);
}

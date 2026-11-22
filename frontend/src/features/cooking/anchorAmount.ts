/** Il numero scritto in «Quanto ne fai?» (R2, secondo modo), letto per il server.
 *
 * Solo la forma: un numero più grande di zero, con la virgola o il punto, fino a sette
 * cifre intere e tre decimali — i tre decimali della colonna `quantity_value`, e sotto i
 * 10 000 000 che il server accetta. Se quel numero vada bene per la ricetta (il limite
 * delle 50 volte) lo dice il server: qui non si sa la dose della ricetta, e non si calcola
 * niente. */

export const AMOUNT_EMPTY = "Scrivi quanto ne fai.";
export const AMOUNT_NOT_A_NUMBER = "Scrivi un numero, come 150 o 1,5.";
export const AMOUNT_ZERO = "Scrivi un numero più grande di zero.";

const NUMBER = /^\d{1,7}(?:[.,]\d{1,3})?$/;

export type AmountReading =
  | { amount: string; problem?: undefined }
  | { amount?: undefined; problem: string };

export function readAmount(text: string): AmountReading {
  const trimmed = text.trim();
  if (trimmed === "") return { problem: AMOUNT_EMPTY };
  if (!NUMBER.test(trimmed)) return { problem: AMOUNT_NOT_A_NUMBER };
  // il server vuole il punto; chi scrive in italiano mette la virgola
  const amount = trimmed.replace(",", ".");
  if (Number(amount) === 0) return { problem: AMOUNT_ZERO };
  return { amount };
}

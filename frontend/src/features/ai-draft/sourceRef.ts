const SOURCE_REF_MAX = 500;

/** `source_ref` sta in 500 caratteri, il prompt può arrivarne a 1000: la provenienza si
 * accorcia, il testo scritto no — quello resta nel suo campo. Senza questo, un prompt
 * lungo faceva rifiutare il salvataggio con un 422. In un modulo suo perché lo usano la
 * bozza da zero e la variante (R8). */
export function sourceRef(prompt: string): string {
  const ref = `prompt: ${prompt}`;
  return ref.length <= SOURCE_REF_MAX ? ref : `${ref.slice(0, SOURCE_REF_MAX - 1)}…`;
}

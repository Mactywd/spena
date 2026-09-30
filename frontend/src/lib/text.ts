/** La prima lettera maiuscola, solo a video (spec T3 §4.7). I nomi dell'anagrafica
 * sono scritti in minuscolo (`Ingredient.name`), e accanto a un `display_name` o al
 * titolo di una sezione si leggevano «a caso» (dal giro). Nessun dato si riscrive: si
 * chiama dove un nome apre una riga, mai dentro una frase («Manca: pasta, uova») e mai
 * in un nome accessibile che lo mette in mezzo a una frase («Togli pasta»). */
export function capitalizeFirst(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** «a» o «ad» davanti a una parola (dal giro di T3: «collegato a astice»). La «d»
 * eufonica solo davanti a una parola che comincia per «a», com'è l'uso di oggi: «ad
 * astice», ma «a erba cipollina», «a olio». */
export function withPrepositionA(word: string): string {
  return /^[aàAÀ]/.test(word) ? `ad ${word}` : `a ${word}`;
}

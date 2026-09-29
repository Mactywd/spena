/** Le frasi che più di uno schermo deve dire allo stesso modo.
 *
 * Sta in un file suo e non accanto al componente che l'ha vista nascere
 * (CatalogSearchPanel) per una ragione meccanica: `react-refresh` vieta a un modulo
 * di componenti di esportare altro, e un modulo condiviso è comunque il posto in cui
 * si cerca una frase che vive in due strade.
 */

/** Il prodotto letto o cercato è di un altro ingrediente, e si dice quale (spec T3
 * §4.3): «è di un altro ingrediente» e basta lasciava a chi ha la confezione in mano il
 * compito di indovinare di quale. Non è un guasto: il tono lo sceglie chi la mostra, e
 * non è il rosso. Il nome arriva dal server (`Product.ingredient_name`). */
export function otherIngredient(productName: string, ingredientName: string): string {
  return `«${productName}» è di un altro ingrediente: ${ingredientName}.`;
}

/** Il catalogo: i prodotti che corrispondono alle parole ma sono di altri ingredienti,
 * contati e nominati — senza, sembrerebbe che il catalogo non li conosca. I nomi senza
 * doppioni: tre yogurt sotto «yogurt bianco» sono un ingrediente, non tre. */
export function elsewhereNote(ingredientNames: string[]): string {
  const distinct = [...new Set(ingredientNames)];
  const names = distinct.join(", ");
  if (ingredientNames.length === 1) {
    return `Un altro prodotto corrisponde, ma è di un altro ingrediente: ${names}.`;
  }
  const whose = distinct.length === 1 ? "di un altro ingrediente" : "di altri ingredienti";
  return `Altri ${ingredientNames.length} prodotti corrispondono, ma sono ${whose}: ${names}.`;
}

/** Le frasi che più di uno schermo deve dire allo stesso modo.
 *
 * Sta in un file suo e non accanto al componente che l'ha vista nascere
 * (CatalogSearchPanel) per una ragione meccanica: `react-refresh` vieta a un modulo
 * di componenti di esportare altro, e un modulo condiviso è comunque il posto in cui
 * si cerca una frase che vive in due strade.
 */

/** Il prodotto esiste ma appartiene a un altro ingrediente.
 *
 * La dicono le due strade che possono agganciare un prodotto a una voce di lista: il
 * filtro della ricerca a catalogo (il prodotto c'è ma non compare) e la lettura del
 * codice a barre (il codice risolve a una referenza di un altro ingrediente). È lo
 * stesso fatto, e dirlo con due frasi diverse lo farebbe sembrare due guasti diversi.
 */
export const OTHER_INGREDIENT = {
  one: "è di un altro ingrediente: non si può agganciare qui",
  many: "sono di un altro ingrediente: non si possono agganciare qui",
};

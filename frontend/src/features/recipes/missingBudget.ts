// La scala del filtro sta qui e non accanto al componente per la ragione scritta in
// pantry/statusLabels.ts: un export costante accanto a un componente rompe il fast
// refresh, e `MAX_BUDGET` lo chiede anche lo schermo del ricettario.

/** I gradini della scala, nell'ordine in cui si leggono.
 *
 * `null` è «Tutte»: non una soglia altissima ma l'assenza di soglia, e il server le
 * distingue — una soglia qualunque gli fa guardare tutto il ricettario invece dei
 * cento più recenti. Oltre i tre mancanti un filtro sui mancanti non filtra più
 * niente, ed è per questo che la scala finisce lì.
 */
export const BUDGET_STEPS: { value: number | null; pill: string; caption: string }[] = [
  { value: null, pill: "Tutte", caption: "Tutto il ricettario." },
  { value: 0, pill: "Ora", caption: "Solo quelle che puoi cucinare adesso." },
  { value: 1, pill: "+1", caption: "Al massimo 1 ingrediente da comprare." },
  { value: 2, pill: "+2", caption: "Al massimo 2 ingredienti da comprare." },
  { value: 3, pill: "+3", caption: "Al massimo 3 ingredienti da comprare." },
];

/** L'ultimo gradino della scala.
 *
 * Lo schermo lo chiede per non dire «alza la soglia» a chi è già in cima: un
 * consiglio impossibile non è un vicolo cieco, ma è la prima frase che si legge
 * quando lo schermo è vuoto, ed è la peggiore da sprecare.
 */
export const MAX_BUDGET = BUDGET_STEPS[BUDGET_STEPS.length - 1].value ?? 0;

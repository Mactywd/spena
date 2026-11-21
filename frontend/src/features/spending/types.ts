// Le spese dell'AI (H1), come le manda `GET /api/v1/llm-spending`. Stanno qui e non in
// `domain/types.ts`: le usa solo questa cartella.

/** I tre periodi, decisi da Mattia: «Questo mese», «Ultimi 30 giorni», «Da sempre». */
export type SpendingPeriod = "month" | "30d" | "all";

export interface SectionSpend {
  call_site: string;
  /** il nome a video, deciso dal server; per una sezione che non conosce, `call_site` com'è */
  label: string;
  cost_usd: number;
  /** la quota del totale, 0–1 */
  share: number;
  calls: number;
}

export interface DaySpend {
  /** il giorno di calendario a Roma, `AAAA-MM-GG` */
  day: string;
  cost_usd: number;
}

export interface Spending {
  period: SpendingPeriod;
  first_day: string;
  last_day: string;
  /** la somma dei costi dichiarati da OpenRouter, in dollari */
  total_usd: number;
  calls: number;
  /** le chiamate senza un costo dichiarato: contate, fuori dal totale */
  unpriced_calls: number;
  /** dalla più cara */
  sections: SectionSpend[];
  /** ogni giorno del periodo, in ordine; quelli senza spesa a 0 */
  days: DaySpend[];
}

import { apiFetch } from "../../api/client";
import type {
  DecideResult,
  ImportStatus,
  ImportTerm,
  RequeueResult,
  SkippedPages,
  TermDecisionResult,
  UndoResult,
} from "../../domain/types";

export function fetchImportStatus() {
  return apiFetch<ImportStatus>("/imports/status");
}

/** Senza `decidedBy`, la coda da decidere: il default del backend (20) è quello
 * pensato per quella lista (vedi `pending_terms` in
 * `backend/app/repositories/imports.py`), quindi non serve dirlo esplicito.
 * Con `decidedBy`, le decisioni già prese da quell'autore, per l'elenco
 * «Decisioni recenti»: qui il `limit` va mandato esplicito a 50, il tetto che la
 * rotta accetta (`le=50`), perché una singola passata dell'AI decide fino a 40
 * termini (`MAX_TERMS_PER_CALL` nel backend) e con il default di 20 metà di quella
 * passata sparirebbe dalla revisione. Le decisioni a mano chiedono lo stesso
 * tetto, così l'elenco fuso non ne ha due. */
export function fetchImportTerms(decidedBy?: "ai" | "human") {
  const query = decidedBy ? `?decided_by=${decidedBy}&limit=50` : "";
  return apiFetch<ImportTerm[]>(`/imports/terms${query}`);
}

/** Un termine solo, deciso o no, nella forma dell'elenco a cui appartiene: quello a
 * cui porta `?termine=` dai rifiuti dell'anagrafica. */
export function fetchImportTerm(id: string) {
  return apiFetch<ImportTerm>(`/imports/terms/${encodeURIComponent(id)}`);
}

/** Fa decidere all'AI i termini in coda, e applica. Non torna proposte da
 * confermare: le decisioni si rivedono dall'elenco «Decisioni recenti». Senza
 * `termIds` vale per tutta la coda, che è il caso del bottone. */
export function decideWithAi(termIds?: string[]) {
  return apiFetch<DecideResult>("/imports/terms/decide", {
    method: "POST",
    body: JSON.stringify(termIds ? { term_ids: termIds } : {}),
  });
}

/** Rimette un termine deciso in coda, e con lui le ricette che ne erano nate. Non
 * chiede conferma: dalla S9 le cotture delle ricette rifatte non si perdono,
 * aspettano nella pagina e tornano sulla ricetta nuova. */
export function undoTerm(termId: string) {
  return apiFetch<UndoResult>(`/imports/terms/${termId}/undo`, { method: "POST" });
}

export function decideTerm(
  termId: string,
  body: {
    action: "map" | "create" | "ignore";
    ingredient_id?: string;
    name?: string;
    display_name?: string;
    category?: string;
    role_override?: "primary" | "secondary";
  }
) {
  return apiFetch<TermDecisionResult>(`/imports/terms/${termId}/decision`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/** Quante pagine scartate per volta: il default della rotta. */
export const SKIPPED_PAGE_SIZE = 50;

/** La chiave dell'elenco delle scartate. Sotto `import-status` di proposito: decidere un
 * termine, chiedere all'AI e annullare possono scartare una pagina, e tutte e tre le
 * mutazioni della coda invalidano già `["import-status"]` — così rileggono anche questo
 * elenco senza che il loro codice lo sappia. */
export const SKIPPED_PAGES_KEY = ["import-status", "skipped-pages"] as const;

/** Le pagine scaricate che non sono diventate ricette, col perché, a partire da `offset`. */
export function fetchSkippedPages(offset: number) {
  return apiFetch<SkippedPages>(
    `/imports/pages/skipped?limit=${SKIPPED_PAGE_SIZE}&offset=${offset}`
  );
}

/** Rimette in coda una pagina scartata. Il backend la materializza subito e risponde com'è
 * finita: entrata, di nuovo scartata, o in attesa di termini da decidere. */
export function requeuePage(pageId: string) {
  return apiFetch<RequeueResult>(`/imports/pages/${encodeURIComponent(pageId)}/requeue`, {
    method: "POST",
  });
}

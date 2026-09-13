import { apiFetch } from "../../api/client";
import type {
  DecideResult,
  ImportStatus,
  ImportTerm,
  TermDecisionResult,
  UndoResult,
} from "../../domain/types";

export function fetchImportStatus() {
  return apiFetch<ImportStatus>("/imports/status");
}

export function fetchImportTerms(decidedBy?: "ai") {
  const query = decidedBy ? `?decided_by=${decidedBy}` : "";
  return apiFetch<ImportTerm[]>(`/imports/terms${query}`);
}

/** Fa decidere all'AI i termini in coda, e applica. Non torna proposte da
 * confermare: le decisioni si rivedono dall'elenco «Deciso dall'AI». Senza
 * `termIds` vale per tutta la coda, che è il caso del bottone. */
export function decideWithAi(termIds?: string[]) {
  return apiFetch<DecideResult>("/imports/terms/decide", {
    method: "POST",
    body: JSON.stringify(termIds ? { term_ids: termIds } : {}),
  });
}

/** Rimette un termine deciso in coda, e con lui le ricette che ne erano nate.
 * `force` supera il 409 che avvisa di uno storico di cottura da scollegare. */
export function undoTerm(termId: string, force = false) {
  return apiFetch<UndoResult>(`/imports/terms/${termId}/undo`, {
    method: "POST",
    body: JSON.stringify({ force }),
  });
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

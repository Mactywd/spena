import { apiFetch } from "../../api/client";
import type {
  ImportStatus,
  ImportTerm,
  TermDecisionResult,
  TermProposal,
} from "../../domain/types";

export function fetchImportStatus() {
  return apiFetch<ImportStatus>("/imports/status");
}

export function fetchImportTerms() {
  return apiFetch<ImportTerm[]>("/imports/terms");
}

/** Le proposte di Claude, in una chiamata separata dall'elenco di proposito: la coda
 * deve caricarsi subito, e un guasto del modello non deve svuotare una schermata che
 * funziona anche senza. */
export function fetchTermProposals(termIds: string[]) {
  return apiFetch<{ proposals: TermProposal[] }>("/imports/terms/proposals", {
    method: "POST",
    body: JSON.stringify({ term_ids: termIds }),
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

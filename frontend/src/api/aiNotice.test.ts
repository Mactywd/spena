import { describe, expect, it } from "vitest";
import { ApiError } from "./client";
import { aiNoticeOf } from "./aiNotice";

// Frase copiata esatta dalla spec §5 (llm-haiku-design): chi la cambia, cambia la spec.
const CREDITO =
  "L'AI non risponde: il credito della chiave API è finito. Va ricaricato nella console di Anthropic.";

describe("aiNoticeOf", () => {
  it("dà la frase di un 503 con un codice llm_", () => {
    const error = new ApiError(CREDITO, 503, { code: "llm_credit", detail: CREDITO });
    expect(aiNoticeOf(error)).toBe(CREDITO);
  });

  it("dà null per un 503 senza codice", () => {
    expect(aiNoticeOf(new ApiError("giù", 503, { detail: "giù" }))).toBeNull();
  });

  it("dà null per un codice che non è llm_", () => {
    expect(aiNoticeOf(new ApiError("x", 503, { code: "claude_busy", detail: "occupato" }))).toBeNull();
  });

  it("dà null se lo status non è 503", () => {
    expect(aiNoticeOf(new ApiError(CREDITO, 500, { code: "llm_credit", detail: CREDITO }))).toBeNull();
  });

  it("dà null per un detail vuoto o non stringa", () => {
    expect(aiNoticeOf(new ApiError("x", 503, { code: "llm_credit", detail: "" }))).toBeNull();
    expect(aiNoticeOf(new ApiError("x", 503, { code: "llm_credit", detail: 5 }))).toBeNull();
  });

  it("dà null per un corpo che non è un oggetto, un errore qualunque e undefined", () => {
    expect(aiNoticeOf(new ApiError("x", 503, null))).toBeNull();
    expect(aiNoticeOf(new Error("boom"))).toBeNull();
    expect(aiNoticeOf(undefined)).toBeNull();
  });
});

import { describe, expect, it } from "vitest";
import { ApiError, UnauthorizedError } from "../api/client";
import { defaultQueryRetryPredicate } from "./queryRetry";

// Il predicato vero, quello che App.tsx dà al suo QueryClient: i test di schermata si
// costruiscono il client con `retry: false` e non lo vedono mai (prima lezione di
// CLAUDE.md). `count` è il numero di tentativi già falliti oltre al primo.
describe("defaultQueryRetryPredicate", () => {
  it.each([
    ["un 500", new ApiError("errore 500", 500)],
    ["un 502 di Nginx", new ApiError("errore 502", 502)],
    ["un 409", new ApiError("conflitto", 409)],
    ["una rete che non risponde", new TypeError("Failed to fetch")],
  ])("%s si ritenta, due volte e non di più", (_nome, error) => {
    expect(defaultQueryRetryPredicate(0, error)).toBe(true);
    expect(defaultQueryRetryPredicate(1, error)).toBe(true);
    expect(defaultQueryRetryPredicate(2, error)).toBe(false);
  });

  it.each([
    ["un 401 (la sessione è scaduta)", new UnauthorizedError()],
    ["un 404 (la cosa chiesta non c'è)", new ApiError("ricetta inesistente", 404)],
  ])("%s non si ritenta mai", (_nome, error) => {
    expect(defaultQueryRetryPredicate(0, error)).toBe(false);
  });
});

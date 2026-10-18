import { MutationObserver } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import { ApiError, UnauthorizedError } from "../api/client";
import { createTestQueryClient } from "../test/queryClient";
import { createAppQueryClient } from "./queryClient";
import { defaultQueryRetryPredicate } from "./queryRetry";

describe("il client react-query dell'app", () => {
  it("ritenta col predicato dell'app, quello che finisce", () => {
    const client = createAppQueryClient(() => {});
    expect(client.getDefaultOptions().queries?.retry).toBe(defaultQueryRetryPredicate);
  });

  it("un 401 da una lettura riporta all'accesso; un altro guasto no", async () => {
    const onUnauthorized = vi.fn();
    const client = createAppQueryClient(onUnauthorized);
    await client
      .fetchQuery({ queryKey: ["guasto"], queryFn: () => Promise.reject(new ApiError("rotto", 500)), retryDelay: 0 })
      .catch(() => {});
    expect(onUnauthorized).not.toHaveBeenCalled();
    await client
      .fetchQuery({ queryKey: ["scaduta"], queryFn: () => Promise.reject(new UnauthorizedError()) })
      .catch(() => {});
    expect(onUnauthorized).toHaveBeenCalledOnce();
  });

  it("un 401 da una scrittura riporta all'accesso", async () => {
    const onUnauthorized = vi.fn();
    const client = createAppQueryClient(onUnauthorized);
    const scrittura = new MutationObserver(client, {
      mutationFn: () => Promise.reject(new UnauthorizedError()),
    });
    await scrittura.mutate().catch(() => {});
    expect(onUnauthorized).toHaveBeenCalledOnce();
  });
});

describe("il client dei test", () => {
  it("è quello dell'app, senza l'attesa fra un tentativo e l'altro", () => {
    const queries = createTestQueryClient().getDefaultOptions().queries;
    expect(queries?.retry).toBe(defaultQueryRetryPredicate);
    expect(queries?.retryDelay).toBe(0);
  });

  it("un guasto permanente si prova tre volte, come in produzione, e poi si dice", async () => {
    const queryFn = vi.fn(() => Promise.reject(new ApiError("rotto", 500)));
    const client = createTestQueryClient();
    await expect(client.fetchQuery({ queryKey: ["sempre-rotto"], queryFn })).rejects.toThrow("rotto");
    expect(queryFn).toHaveBeenCalledTimes(3);
  });
});

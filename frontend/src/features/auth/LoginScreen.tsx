import { useState } from "react";
import type { FormEvent } from "react";
import { apiFetch } from "../../api/client";

export function LoginScreen({ onSuccess }: { onSuccess: () => void }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await apiFetch("/auth/login", {
        method: "POST",
        body: JSON.stringify({ password }),
      });
      onSuccess();
    } catch {
      setError("Password errata");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="mx-auto flex max-w-sm flex-col gap-4 p-6 pt-24">
      <h1 className="text-2xl font-semibold">Spena</h1>
      <label htmlFor="password" className="text-sm text-neutral-600">Password</label>
      <input
        id="password"
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        className="rounded-lg border border-neutral-300 px-3 py-3 text-base"
        autoComplete="current-password"
      />
      {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
      <button
        type="submit"
        disabled={busy || password.length === 0}
        className="rounded-lg bg-emerald-700 px-4 py-3 text-white disabled:opacity-40"
      >
        Entra
      </button>
    </form>
  );
}

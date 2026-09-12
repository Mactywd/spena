import { useState } from "react";
import type { FormEvent } from "react";
import { apiFetch, UnauthorizedError } from "../../api/client";
import { Alert } from "../../components/ui/Alert";
import { buttonClasses } from "../../components/ui/buttonClasses";

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
    } catch (failure) {
      // solo un 401 dice qualcosa sulla password: chiamare "errata" un server
      // spento manda a riprovare il tasto giusto convinti che sia sbagliato
      setError(
        failure instanceof UnauthorizedError
          ? "Password errata"
          : "Impossibile contattare il server. Riprova."
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-dvh items-center justify-center p-6">
      <form onSubmit={submit} className="w-full max-w-sm">
        {/* il marchio prima del campo: è l'unica schermata dove l'app si presenta,
            e quella in cui si arriva senza sapere se si è nel posto giusto */}
        <div className="pb-6 text-center">
          {/* lo stesso cesto dell'icona sul telefono: chi apre l'app installata
              deve ritrovare qui il segno che ha toccato sulla schermata iniziale */}
          <svg viewBox="0 0 512 512" aria-hidden="true" className="inline-block size-16">
            <rect width="512" height="512" rx="112" fill="var(--color-brand)" />
            <g fill="none" stroke="#fff" strokeLinecap="round" strokeLinejoin="round">
              <path d="M148 218h216l-42 142H190z" strokeWidth="26" />
              <path d="M194 218a62 62 0 0 1 124 0" strokeWidth="26" />
              <path d="M219 254l9 76M293 254l-9 76" strokeWidth="22" />
            </g>
          </svg>
          <h1 className="pt-3 text-2xl font-semibold tracking-tight">Spena</h1>
        </div>
        <div className="flex flex-col gap-4 rounded-card bg-card p-5">
          <label htmlFor="password" className="text-sm font-medium text-ink-soft">
            Password
          </label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="-mt-2"
            autoComplete="current-password"
          />
          {error && <Alert>{error}</Alert>}
          <button
            type="submit"
            disabled={busy || password.length === 0}
            className={buttonClasses("primary", "block")}
          >
            Entra
          </button>
        </div>
      </form>
    </div>
  );
}

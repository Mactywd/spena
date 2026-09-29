import { useState } from "react";
import type { FormEvent } from "react";
import { apiFetch, UnauthorizedError } from "../../api/client";
import { Alert } from "../../components/ui/Alert";
import { BrandMark } from "../../components/ui/BrandMark";
import { Button } from "../../components/ui/Button";
import { IconEye, IconEyeOff } from "../../components/ui/icons";

export function LoginScreen({ onSuccess }: { onSuccess: () => void }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // «Mostra password» (spec T3 §4.7): sul telefono un tasto sbagliato non si vede
  const [shown, setShown] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    // `Button` rifiuta già tocco e Invio quando «Entra» è in volo o non ancora pronto:
    // la guardia resta qui perché un invio arrivato per un'altra strada non parta a vuoto
    if (busy || password.length === 0) return;
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
          <BrandMark className="inline-block size-16" />
          <h1 className="pt-3 text-2xl font-semibold tracking-tight">Spena</h1>
        </div>
        <div className="flex flex-col gap-4 rounded-card bg-card p-5">
          <label htmlFor="password" className="text-sm font-medium text-ink-soft">
            Password
          </label>
          <div className="-mt-2 flex items-center gap-2">
            <input
              id="password"
              type={shown ? "text" : "password"}
              value={password}
              onChange={(e) => {
                setPassword(e.target.value);
                // l'errore parlava della password di prima: riscrivendola non vale più
                setError(null);
              }}
              // l'unica cosa da fare qui: il campo prende il fuoco appena si apre
              autoFocus
              // mostrata, resta una password: niente maiuscola d'ufficio né correttore
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck={false}
              autoComplete="current-password"
              className="min-w-0 flex-1"
            />
            {/* un interruttore di sola icona (Consegna 6a): il nome resta fisso,
                `aria-pressed` dice se la password è in vista, l'icona lo mostra */}
            <Button
              variant="ghost"
              icon={shown ? IconEyeOff : IconEye}
              label="Mostra password"
              aria-pressed={shown}
              onClick={() => setShown((visible) => !visible)}
            />
          </div>
          {error && <Alert>{error}</Alert>}
          {/* in un contenitore suo: il perché che Button scrive sotto «Entra» gli sta
              attaccato, e non a 16 px come le righe di questa colonna */}
          <div>
            <Button
              type="submit"
              variant="primary"
              shape="block"
              busy={busy}
              unavailableReason={password.length === 0 ? "Scrivi la password per entrare." : undefined}
            >
              Entra
            </Button>
          </div>
        </div>
      </form>
    </div>
  );
}

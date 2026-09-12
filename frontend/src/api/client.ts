const BASE = "/api/v1";

export class ApiError extends Error {
  readonly status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export class UnauthorizedError extends ApiError {
  constructor() {
    super("sessione scaduta", 401);
    this.name = "UnauthorizedError";
  }
}

/** Il corpo d'errore di FastAPI ridotto a una frase. `detail` è una stringa per
 * gli errori che solleviamo noi, ma su un 422 di validazione è una lista di
 * oggetti, ognuno con il suo `msg`: passata nuda a `new Error` diventa
 * "[object Object]". Nessuno schermo mostra `message` grezzo oggi — ramificano
 * tutti su `status` — quindi questa è una riserva per chi legge una console, non
 * un testo da mostrare: l'autorità resta `status`. */
function detailToMessage(detail: unknown, status: number): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const joined = detail
      .map((entry) =>
        entry !== null && typeof entry === "object" && "msg" in entry
          ? String((entry as { msg: unknown }).msg)
          : String(entry)
      )
      .filter((message) => message !== "")
      .join("; ");
    if (joined !== "") return joined;
  }
  return `errore ${status}`;
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    // il cookie di sessione è HttpOnly: va mandato dal browser, non da noi
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
  });

  if (response.status === 401) throw new UnauthorizedError();
  if (response.status === 204) return null as T;

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(detailToMessage(body?.detail, response.status), response.status);
  }
  return (await response.json()) as T;
}

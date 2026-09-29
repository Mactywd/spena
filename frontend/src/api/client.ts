const BASE = "/api/v1";

export class ApiError extends Error {
  readonly status: number;
  /** Il corpo d'errore così come è arrivato, `null` se non era JSON. Serve a chi
   * sa che una risposta porta più di `detail`: il 409 di `POST /ingredients` porta
   * l'ingrediente omonimo in `existing` (S19). */
  readonly body: unknown;
  constructor(message: string, status: number, body: unknown = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
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

/** La richiesta e i suoi errori, in un posto solo: `apiFetch` e `apiFetchWithHeaders`
 * ne leggono poi il corpo. Due copie di questi controlli si scollerebbero proprio sul
 * 401, che è quello che riporta all'accesso. */
async function request(path: string, init: RequestInit): Promise<Response> {
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    // il cookie di sessione è HttpOnly: va mandato dal browser, non da noi
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
  });

  if (response.status === 401) throw new UnauthorizedError();

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(detailToMessage(body?.detail, response.status), response.status, body);
  }
  return response;
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await request(path, init);
  if (response.status === 204) return null as T;
  return (await response.json()) as T;
}

/** Il corpo e le intestazioni, per chi legge nella risposta più del corpo: il totale del
 * ricettario sta in `X-Total-Count` (T3 Consegna 4), perché il corpo di
 * `GET /recipes/search` resta una lista per i frontend vecchi in cache. */
export async function apiFetchWithHeaders<T>(
  path: string,
  init: RequestInit = {}
): Promise<{ data: T; headers: Headers }> {
  const response = await request(path, init);
  const data = response.status === 204 ? (null as T) : ((await response.json()) as T);
  return { data, headers: response.headers };
}

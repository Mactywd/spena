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
    const detail = await response.json().catch(() => null);
    throw new ApiError(detail?.detail ?? `errore ${response.status}`, response.status);
  }
  return (await response.json()) as T;
}

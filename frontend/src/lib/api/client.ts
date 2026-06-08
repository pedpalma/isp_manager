// Cliente de API tipado e ciente de contexto.

import type { ApiErrorBody, HealthDBResponse, HealthResponse } from "./types";

const DEFAULT_TIMEOUT_MS = 8000;
const FALLBACK_BASE_URL = "http://localhost:8000";

/** Escolhe a base URL conforme o código roda no navegador ou no servidor. */
function resolveBaseUrl(): string {
  const isServer = typeof window === "undefined";
  if (isServer) {
    return (
      process.env.INTERNAL_API_URL ??
      process.env.NEXT_PUBLIC_API_URL ??
      FALLBACK_BASE_URL
    );
  }
  // No navegador, só variáveis NEXT_PUBLIC_* são embutidas no bundle.
  return process.env.NEXT_PUBLIC_API_URL ?? FALLBACK_BASE_URL;
}

/** UUID por requisição. crypto.randomUUID existe em navegadores atuais e no Node 19+. */
function newRequestId(): string {
  if (
    typeof crypto !== "undefined" &&
    typeof crypto.randomUUID === "function"
  ) {
    return crypto.randomUUID();
  }
  return `${Date.now().toString(16)}-${Math.random().toString(16).slice(2)}`;
}

function safeJsonParse(raw: string): unknown {
  try {
    return JSON.parse(raw);
  } catch {
    return raw;
  }
}

/** Erro tipado de API. Carrega o suficiente para log e UI. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details?: unknown;
  readonly requestId: string | null;

  constructor(args: {
    status: number;
    code: string;
    message: string;
    details?: unknown;
    requestId?: string | null;
  }) {
    super(args.message);
    this.name = "ApiError";
    this.status = args.status;
    this.code = args.code;
    this.details = args.details;
    this.requestId = args.requestId ?? null;
  }
}

export interface RequestOptions {
  method?: string;
  /** Corpo serializável em JSON (objeto) ou undefined. */
  body?: unknown;
  /** Cabeçalhos extras. */
  headers?: Record<string, string>;
  /**
   * Envia X-Request-ID gerado no cliente (default: true).
   * Desligar evita o preflight CORS em GETs simples (hot paths de leitura).
   */
  sendRequestId?: boolean;
  /** Timeout por requisição (ms). */
  timeoutMs?: number;
  /** Repasse cru ao fetch (cache, next.revalidate, signal externo, etc.). */
  init?: RequestInit;
}

export interface ApiResponse<T> {
  data: T;
  status: number;
  requestId: string | null;
}

async function request<T>(
  path: string,
  options: RequestOptions = {},
): Promise<ApiResponse<T>> {
  const {
    method = "GET",
    body,
    headers = {},
    sendRequestId = true,
    timeoutMs = DEFAULT_TIMEOUT_MS,
    init = {},
  } = options;

  const url = `${resolveBaseUrl()}${path}`;

  const finalHeaders: Record<string, string> = { ...headers };
  if (body !== undefined) {
    finalHeaders["Content-Type"] = "application/json";
  }
  if (sendRequestId && finalHeaders["X-Request-ID"] === undefined) {
    finalHeaders["X-Request-ID"] = newRequestId();
  }

  // Timeout via AbortController. Se houver signal externo, ele tem prioridade.
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  let res: Response;
  try {
    res = await fetch(url, {
      ...init,
      method,
      headers: finalHeaders,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: init.signal ?? controller.signal,
    });
  } catch (err) {
    const aborted = err instanceof DOMException && err.name === "AbortError";
    throw new ApiError({
      status: 0,
      code: aborted ? "timeout" : "network_error",
      message: aborted
        ? "A requisição à API expirou."
        : "Falha de rede ao contatar a API.",
      requestId: finalHeaders["X-Request-ID"] ?? null,
    });
  } finally {
    clearTimeout(timeout);
  }

  const requestId = res.headers.get("X-Request-ID");
  const raw = await res.text();
  const parsed: unknown = raw ? safeJsonParse(raw) : null;

  if (!res.ok) {
    const envelope = parsed as Partial<ApiErrorBody> | null;
    const errorObj = envelope?.error;
    throw new ApiError({
      status: res.status,
      code: errorObj?.code ?? "http_error",
      message: errorObj?.message ?? `Erro HTTP ${res.status}.`,
      details: errorObj?.details,
      requestId: errorObj?.request_id ?? requestId,
    });
  }

  return { data: parsed as T, status: res.status, requestId };
}

/**
 * Superfície pública do cliente. Cresce por domínio nos próximos marcos
 * (ex.: api.olts.list(), api.onus.provision(...)).
 */
export const api = {
  request,
  health: () => request<HealthResponse>("/health"),
  healthDb: () => request<HealthDBResponse>("/health/db"),
};

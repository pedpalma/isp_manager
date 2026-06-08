// Tipos compartilhados do cliente de API.
// Espelham os contratos do backend para o frontend não "adivinhar" formatos.

// GET /health  (espelha HealthResponse do backend: liveness, não toca em deps).
export interface HealthResponse {
  status: "ok";
}

// GET /health/db  (espelha HealthDBResponse: readiness do banco).
export interface HealthDBResponse {
  status: "ok";
  database: "reachable";
}

// Envelope de erro padronizado do backend (Marco 6).
// Toda falha TRATADA chega neste formato. Mantemos os campos opcionais
// porque erros de rede/timeout no cliente não têm corpo do servidor.
export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details?: unknown;
    request_id?: string | null;
  };
}

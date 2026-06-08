import { NextResponse } from "next/server";

// Liveness do PRÓPRIO frontend (não consulta a API).
// É o alvo do healthcheck do container: barato e não depende de compilar a
// página inteira no primeiro acesso, evitando que o healthcheck "pisque".
export const dynamic = "force-dynamic";

export function GET() {
  return NextResponse.json({ status: "ok" });
}

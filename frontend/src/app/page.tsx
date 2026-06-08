"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, api } from "@/lib/api/client";
import type { HealthResponse } from "@/lib/api/types";

const POLL_INTERVAL_MS = 10_000;

type Probe =
  | { state: "loading" }
  | {
      state: "ok";
      latencyMs: number;
      requestId: string | null;
      payload: HealthResponse;
    }
  | { state: "error"; message: string; status: number; requestId: string | null };

export default function HomePage() {
  const [probe, setProbe] = useState<Probe>({ state: "loading" });
  const [polling, setPolling] = useState(true);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);

  const check = useCallback(async () => {
    setProbe((prev) => (prev.state === "loading" ? prev : { state: "loading" }));
    const startedAt = performance.now();
    try {
      const res = await api.health();
      setProbe({
        state: "ok",
        latencyMs: Math.round(performance.now() - startedAt),
        requestId: res.requestId,
        payload: res.data,
      });
    } catch (err) {
      if (err instanceof ApiError) {
        setProbe({
          state: "error",
          message: err.message,
          status: err.status,
          requestId: err.requestId,
        });
      } else {
        setProbe({
          state: "error",
          message: "Erro inesperado ao consultar a API.",
          status: 0,
          requestId: null,
        });
      }
    } finally {
      setLastChecked(new Date());
    }
  }, []);

  useEffect(() => {
    void check();
  }, [check]);

  useEffect(() => {
    if (!polling) return;
    const id = setInterval(() => void check(), POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [polling, check]);

  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col justify-center gap-8 px-6 py-16">
      <header className="space-y-2">
        <p className="text-xs font-medium uppercase tracking-[0.2em] text-neutral-400">
          ISP Manager
        </p>
        <h1 className="text-3xl font-semibold tracking-tight text-neutral-900">
          Status da API
        </h1>
        <p className="text-sm text-neutral-500">
          Consulta de <code className="font-mono text-neutral-700">/health</code>{" "}
          feita pelo navegador. Valida o caminho cross-origin (CORS) que as telas
          seguintes vão usar.
        </p>
      </header>

      <StatusCard probe={probe} />

      <div className="flex items-center justify-between border-t border-neutral-200 pt-4 text-sm text-neutral-500">
        <span className="tabular-nums">
          {lastChecked
            ? `Última verificação ${lastChecked.toLocaleTimeString("pt-BR")}`
            : "Verificando..."}
        </span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => void check()}
            className="rounded-md border border-neutral-300 bg-white px-3 py-1.5 font-medium text-neutral-700 transition hover:bg-neutral-100 active:translate-y-px"
          >
            Verificar agora
          </button>
          <button
            type="button"
            onClick={() => setPolling((p) => !p)}
            className="rounded-md px-3 py-1.5 font-medium text-neutral-500 transition hover:bg-neutral-100"
          >
            {polling ? "Pausar" : "Retomar"} ({POLL_INTERVAL_MS / 1000}s)
          </button>
        </div>
      </div>
    </main>
  );
}

function StatusCard({ probe }: { probe: Probe }) {
  const base = "rounded-2xl border p-6 shadow-sm transition-colors";

  if (probe.state === "loading") {
    return (
      <section className={`${base} border-neutral-200 bg-white`}>
        <div className="flex items-center gap-3">
          <span className="status-pulse inline-block h-3 w-3 rounded-full bg-neutral-300" />
          <p className="font-medium text-neutral-500">Consultando /health...</p>
        </div>
      </section>
    );
  }

  if (probe.state === "ok") {
    return (
      <section className={`${base} border-emerald-200 bg-emerald-50/70`}>
        <div className="flex items-center gap-3">
          <span className="status-pulse inline-block h-3 w-3 rounded-full bg-emerald-500" />
          <p className="text-lg font-semibold text-emerald-800">API online</p>
        </div>
        <MetaList
          tone="emerald"
          rows={[
            ["status", probe.payload.status],
            ["latência", `${probe.latencyMs} ms`],
            ["request_id", probe.requestId ?? "n/d"],
          ]}
        />
      </section>
    );
  }

  return (
    <section className={`${base} border-red-200 bg-red-50/70`}>
      <div className="flex items-center gap-3">
        <span className="inline-block h-3 w-3 rounded-full bg-red-500" />
        <p className="text-lg font-semibold text-red-800">API indisponível</p>
      </div>
      <MetaList
        tone="red"
        rows={[
          ["mensagem", probe.message],
          ["HTTP", probe.status ? String(probe.status) : "sem resposta"],
          ["request_id", probe.requestId ?? "n/d"],
        ]}
      />
    </section>
  );
}

function MetaList({
  rows,
  tone,
}: {
  rows: Array<[string, string]>;
  tone: "emerald" | "red";
}) {
  const labelColor = tone === "emerald" ? "text-emerald-700/70" : "text-red-700/70";
  const valueColor = tone === "emerald" ? "text-emerald-900" : "text-red-900";
  return (
    <dl className="mt-4 space-y-2 text-sm">
      {rows.map(([label, value]) => (
        <div key={label} className="flex items-baseline justify-between gap-4">
          <dt className={`shrink-0 ${labelColor}`}>{label}</dt>
          <dd className={`truncate text-right font-mono ${valueColor}`}>{value}</dd>
        </div>
      ))}
    </dl>
  );
}

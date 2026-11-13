"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { CommThreadPanel } from "@/components/comm";
import { PendingList } from "@/components/proposals";
import { api, ApiError } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";

interface Item {
  id: string; kind: string; case_code: string | null; case_title: string | null; contact: string;
  last_message_at: string; last_from: string; unread: number; urgent_unconfirmed: number;
}
interface Inbox { threads: Item[]; totals: { unread: number; urgent_unconfirmed: number } }

const FILTERS = { todos: "Todas", sin_leer: "Sin leer", urgentes: "Urgentes sin confirmar", aprobar: "Mensajes por aprobar" } as const;

function Bandeja() {
  const params = useSearchParams();
  const [filter, setFilter] = useState<keyof typeof FILTERS>(params.get("filtro") === "aprobar" ? "aprobar" : "todos");
  const [d, setD] = useState<Inbox | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [sel, setSel] = useState<string | null>(params.get("hilo"));
  const [toApprove, setToApprove] = useState<number | null>(null);
  const load = useCallback(() => api<Inbox>(`/comm/inbox?filter=${filter === "aprobar" ? "todos" : filter}`).then((r) => { setD(r); setErr(null); })
    .catch((e) => setErr(e instanceof ApiError ? e.message : "No disponible")), [filter]);
  useEffect(() => { load(); const t = setInterval(load, 20000); return () => clearInterval(t); }, [load]);
  return (
    <div className="stack">
      <div className="topline">
        <div>
          <h1>Comunicaciones</h1>
          <p className="subtitle">Conversaciones con los clientes en el portal del despacho, una por expediente y otra general por cliente. Sustituye a WhatsApp: todo queda en el expediente y nada se borra.</p>
        </div>
      </div>
      {err && <div className="notice notice-danger" role="alert">{err}</div>}
      <div className="tabs" role="tablist">
        {(Object.keys(FILTERS) as (keyof typeof FILTERS)[]).map((f) => (
          <button key={f} role="tab" aria-selected={filter === f} onClick={() => setFilter(f)}>
            {FILTERS[f]}{f === "sin_leer" && d?.totals.unread ? ` (${d.totals.unread})` : ""}{f === "urgentes" && d?.totals.urgent_unconfirmed ? ` (${d.totals.urgent_unconfirmed})` : ""}{f === "aprobar" && toApprove ? ` (${toApprove})` : ""}
          </button>
        ))}
      </div>
      <div hidden={filter !== "aprobar"}>
        <p className="small muted">Mensajes que el agente ha preparado con las plantillas aprobadas (bienvenida, avisos y recordatorios de conciliaciones y juicios, seguimiento). Se envían por el portal del cliente cuando usted los aprueba.</p>
        <PendingList params={{ agent: "mensajes" }} decided onCount={setToApprove} empty="No hay mensajes pendientes de aprobar." />
      </div>
      <div className="inbox-layout" hidden={filter === "aprobar"}>
        <div className="inbox-list" aria-label="Bandeja de conversaciones">
          {d === null && <p className="muted">Cargando…</p>}
          {d?.threads.length === 0 && <p className="muted small">No hay conversaciones{filter !== "todos" ? " con este filtro" : ""}. Las conversaciones se abren desde cada expediente o desde la ficha del cliente.</p>}
          {d?.threads.map((t) => (
            <button key={t.id} className="inbox-item" aria-current={sel === t.id} onClick={() => { setSel(t.id); setTimeout(load, 800); }}>
              <div className="row"><strong>{t.contact}</strong>{t.unread > 0 && <span className="count" aria-label={`${t.unread} sin leer`}>{t.unread}</span>}</div>
              <span className="small mono">{t.case_code ?? "Conversación general"}</span>
              <span className="small muted">{fmtDateTime(t.last_message_at)} · último: {t.last_from === "cliente" ? "el cliente" : t.last_from === "nota" ? "nota interna" : "el despacho"}</span>
              {t.urgent_unconfirmed > 0 && <span className="badge badge-red small">{t.urgent_unconfirmed} urgente(s) sin confirmar</span>}
            </button>
          ))}
        </div>
        <div style={{ minWidth: 0 }}>
          {sel ? <CommThreadPanel key={sel} threadId={sel} /> : <div className="card"><p className="muted">Elija una conversación de la lista.</p></div>}
        </div>
      </div>
    </div>
  );
}

export default function ComunicacionesPage() {
  return <Suspense fallback={<p className="muted">Cargando…</p>}><Bandeja /></Suspense>;
}

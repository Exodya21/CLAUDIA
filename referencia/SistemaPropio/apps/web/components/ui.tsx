"use client";

import Link from "next/link";
import type { ModuleInfo } from "@/lib/modules";
import { FASES, LEAD_ESTADOS, MATERIAS, TAREA_ESTADOS, TAREA_TIPOS, label } from "@/lib/format";

export function MateriaBadge({ materia }: { materia: string }) {
  const cls = materia === "laboral" ? "badge-blue" : materia === "extranjeria" ? "badge-yellow" : "badge-green";
  return <span className={`badge ${cls}`}>{label(MATERIAS, materia)}</span>;
}

export function EstadoBadge({ status }: { status: string }) {
  const cls = status === "resuelto" || status === "archivado" ? "badge-green" : status === "suspendido" || status === "preapertura" ? "badge-yellow" : "";
  return <span className={`badge ${cls}`}>{label(FASES, status)}</span>;
}

export function LeadStatusBadge({ s }: { s: string }) {
  const cls = s === "convertido" ? "badge-green" : s === "descartado" || s === "no_convertido" ? "" : s === "nuevo" ? "badge-yellow" : "badge-blue";
  return <span className={`badge ${cls}`}>{label(LEAD_ESTADOS, s)}</span>;
}

const KIND_COLOR: Record<string, string> = { senalamiento: "badge-red", conciliacion: "badge-yellow", plazo: "badge-red", gestion: "badge-blue", llamada: "", otro: "" };
export function KindBadge({ kind }: { kind: string }) {
  return <span className={`badge ${KIND_COLOR[kind] ?? ""}`}>{label(TAREA_TIPOS, kind)}</span>;
}
export function TaskStatusBadge({ s }: { s: string }) {
  const cls = s === "completada" ? "badge-green" : s === "pospuesta" ? "badge-yellow" : s === "en_curso" ? "badge-blue" : "";
  return <span className={`badge ${cls}`}>{label(TAREA_ESTADOS, s)}</span>;
}
export function LegalBadge({ status, date }: { status: string; date: string | null }) {
  if (status === "no_aplica" || !date) return null;
  const d = date.split("-").reverse().join("/");
  return status === "validado"
    ? <span className="badge badge-green" title="Plazo legal validado por letrado">Plazo legal {d} · validado</span>
    : <span className="badge badge-red" title="Propuesto, pendiente de validación letrada">Plazo legal {d} · SIN VALIDAR</span>;
}

export function AccessBadge({ level }: { level: string }) {
  if (level === "full") return <span className="badge badge-green">Acceso completo</span>;
  if (level === "metadata") return <span className="badge">Solo metadatos</span>;
  return <span className="badge">Ficha mínima</span>;
}

export function Pager({ page, pageSize, total, onPage }: { page: number; pageSize: number; total: number; onPage: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="pager" aria-label="Paginación">
      <span>{total} resultado{total === 1 ? "" : "s"} · página {page} de {pages}</span>
      <button className="btn btn-sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>Anterior</button>
      <button className="btn btn-sm" disabled={page >= pages} onClick={() => onPage(page + 1)}>Siguiente</button>
    </div>
  );
}

export function PendingModule({ m }: { m: ModuleInfo }) {
  return (
    <div className="stack">
      <div className="topline">
        <div>
          <h1>{m.label}</h1>
          <p className="subtitle">Módulo {m.code} · fase prevista {m.fase}</p>
        </div>
        <span className="badge badge-yellow">Pendiente de desarrollar</span>
      </div>
      <div className="notice notice-warn">
        <strong>No disponible aún</strong>
        Este módulo todavía no tiene base de datos ni API. No se muestran datos de ejemplo para no simular un
        funcionamiento que no existe.
      </div>
      <div className="card">
        <h2>Qué hará</h2>
        <p>{m.resumen}</p>
        <div className="grid grid-3">
          <div>
            <h3>Requisitos vinculados</h3>
            <div className="chips">{m.requisitos.map((r) => <span key={r} className="badge mono">{r}</span>)}</div>
          </div>
          <div>
            <h3>Pruebas de aceptación</h3>
            <div className="chips">{m.pruebas.length ? m.pruebas.map((r) => <span key={r} className="badge mono">{r}</span>) : <span className="muted">—</span>}</div>
          </div>
          <div>
            <h3>Decisiones que lo bloquean</h3>
            <div className="chips">{m.decisiones.length ? m.decisiones.map((r) => <span key={r} className="badge badge-red mono">{r}</span>) : <span className="muted">Ninguna crítica</span>}</div>
          </div>
        </div>
      </div>
      <p className="small muted">Detalle completo en <span className="mono">docs/producto/backlog_fases.md</span>. <Link href="/">Volver al inicio</Link></p>
    </div>
  );
}

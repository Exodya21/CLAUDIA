"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";

interface OrgState {
  organization_id: string; enabled: boolean; mode: string; version: number; can_manage: boolean; pending: number; errors_24h: number;
  last_run: { at: string; status: string; trigger: string; summary: Record<string, number> | null; error: string | null } | null;
}
interface AgentInfo {
  code: string; name: string; area: string; description: string; covers: string[]; requirements: string[]; events: string[];
  every_min: number | null; can_be_automatic: boolean; limits: string[]; orgs: OrgState[];
}
interface Run { id: string; trigger: string; status: string; started_at: string; summary: Record<string, number> | null; error: string | null }
interface Template { code: string; name: string; dr: string; task_kind: string | null; version: string; text: string }
interface Metrics { days: number; programados: number; por_estado: Record<string, number>; por_plantilla: Record<string, { programados: number; enviados: number; cancelados: number }>; con_respuesta_3_dias: number; duplicados_evitados: number; derivados_al_equipo: number; plantillas_version: string }

const EVENTS: Record<string, string> = {
  "bank.imported": "al importar un extracto", "case.opened": "al abrir un expediente", "case.closed": "al archivar o desistir",
  "task.created": "al poner una conciliación o juicio en la agenda", "task.changed": "al cambiar o anular esa fecha",
};

export function AgentsAdmin() {
  const [list, setList] = useState<AgentInfo[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const load = useCallback(() => api<AgentInfo[]>("/agents").then(setList).catch((e) => setErr(e instanceof ApiError ? e.message : "No disponible")), []);
  useEffect(() => { load(); }, [load]);
  return (
    <div className="stack">
      <p className="subtitle" style={{ margin: 0 }}>Los «motores» de Dirección: piezas del propio sistema que reaccionan a lo que pasa (un extracto, un expediente abierto, una fecha en la agenda) y dejan su trabajo como pendiente en el departamento que corresponde (Contabilidad, Comunicaciones, Recepción, RRHH). Aquí se activan, se pausan y se elige si proponen o actúan solos (solo donde se permite). Todo queda registrado.</p>
      {err && <div className="notice notice-danger" role="alert">{err}</div>}
      {list?.map((a) => <AgentCard key={a.code} a={a} onChanged={load} />)}
      <div className="card">
        <strong>Próximos agentes</strong>
        <p className="small muted" style={{ margin: "4px 0 0" }}>Recepción (cierre diario, DR-REC), RRHH (vencimientos de contratos y documentos, DR-RH) y proveedores/tesorería (DR-CON-4, 7, 8): no disponibles aún. Se añadirán aquí con el mismo motor, sin rehacer nada.</p>
      </div>
    </div>
  );
}

function AgentCard({ a, onChanged }: { a: AgentInfo; onChanged: () => void }) {
  const [runs, setRuns] = useState<Run[] | null>(null);
  const [open, setOpen] = useState(false);
  return (
    <div className="card stack" style={{ gap: 10 }} aria-label={a.name}>
      <div className="row"><h2 style={{ margin: 0 }}>{a.name}</h2><span className="badge">{a.area}</span>
        {a.covers.map((c) => <span key={c} className="badge badge-blue mono">{c}</span>)}</div>
      <p style={{ margin: 0 }}>{a.description}</p>
      <div className="grid grid-2">
        <div>
          <strong className="small">Cuándo trabaja</strong>
          <ul className="small" style={{ margin: "4px 0 0", paddingLeft: 18 }}>
            {a.events.map((e) => <li key={e}>{EVENTS[e] ?? e}</li>)}
            {a.every_min && <li>y cada {a.every_min} minutos por calendario</li>}
          </ul>
        </div>
        <div>
          <strong className="small">Lo que nunca hace</strong>
          <ul className="small" style={{ margin: "4px 0 0", paddingLeft: 18 }}>{a.limits.map((l) => <li key={l}>{l}</li>)}</ul>
        </div>
      </div>
      {a.orgs.map((o) => <OrgSetting key={o.organization_id} a={a} o={o} onChanged={onChanged} />)}
      <div className="row">
        <button className="btn btn-sm" onClick={() => { setOpen(!open); if (!runs) api<Run[]>(`/agents/${a.code}/runs`).then(setRuns).catch(() => setRuns([])); }}>{open ? "Ocultar actividad" : "Ver actividad"}</button>
        <span className="small muted">Requisitos: {a.requirements.join(", ")}</span>
      </div>
      {open && (
        <div className="table-wrap">
          <table className="data">
            <thead><tr><th>Inicio</th><th>Motivo</th><th>Resultado</th><th>Recuento</th></tr></thead>
            <tbody>
              {runs?.length === 0 && <tr><td colSpan={4} className="empty">Aún no ha trabajado.</td></tr>}
              {runs?.map((r) => (
                <tr key={r.id}><td>{fmtDateTime(r.started_at)}</td><td className="small">{r.trigger}</td>
                  <td><span className={`badge ${r.status === "ok" ? "badge-green" : "badge-red"}`}>{r.status}</span>{r.error && <div className="small error-text">{r.error}</div>}</td>
                  <td className="small">{r.summary ? Object.entries(r.summary).map(([k, v]) => `${k.replace(/_/g, " ")}: ${v}`).join(" · ") : "—"}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {a.code === "mensajes" && <MessagesPanel />}
    </div>
  );
}

function OrgSetting({ a, o, onChanged }: { a: AgentInfo; o: OrgState; onChanged: () => void }) {
  const [edit, setEdit] = useState(false);
  const [enabled, setEnabled] = useState(o.enabled);
  const [mode, setMode] = useState(o.mode);
  const [reason, setReason] = useState("");
  const [err, setErr] = useState<string | null>(null);
  async function save(e: React.FormEvent) {
    e.preventDefault(); setErr(null);
    try { await api(`/agents/${a.code}/settings`, { method: "POST", body: JSON.stringify({ organization_id: o.organization_id, enabled, mode, reason }) }); setEdit(false); setReason(""); onChanged(); }
    catch (ex) { setErr(ex instanceof ApiError ? ex.message : "No se pudo guardar"); }
  }
  return (
    <div className="notice notice-info">
      <div className="row">
        <span className={`badge ${o.enabled ? "badge-green" : "badge-red"}`}>{o.enabled ? "Activo" : "En pausa"}</span>
        <span>Modo: <strong>{o.mode === "automatico" ? "automático (envía sin revisión)" : "propone (una persona aprueba)"}</strong></span>
        <span className="small">· {o.pending} pendiente(s) en la bandeja</span>
        {o.errors_24h > 0 && <span className="badge badge-red">{o.errors_24h} error(es) en 24 h</span>}
        {o.last_run && <span className="small muted">· última vez {fmtDateTime(o.last_run.at)}</span>}
        <span className="spacer" />
        {o.can_manage && <button className="btn btn-sm" onClick={() => setEdit(!edit)}>Configurar</button>}
      </div>
      {edit && (
        <form className="row" style={{ marginTop: 8 }} onSubmit={save}>
          <label className="row small"><input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} /> Activo</label>
          <select aria-label="Modo" value={mode} onChange={(e) => setMode(e.target.value)} style={{ width: "auto" }}>
            <option value="propone">Propone (una persona aprueba)</option>
            <option value="automatico" disabled={!a.can_be_automatic}>Automático{a.can_be_automatic ? " (solo tras el piloto, T-47)" : " (no permitido)"}</option>
          </select>
          <input aria-label="Motivo del cambio" value={reason} onChange={(e) => setReason(e.target.value)} minLength={5} required placeholder="Motivo (queda en la auditoría)" style={{ maxWidth: 300 }} />
          <button className="btn btn-sm btn-primary">Guardar</button>
          {err && <span className="error-text small">{err}</span>}
        </form>
      )}
    </div>
  );
}

function MessagesPanel() {
  const [m, setM] = useState<Metrics | null>(null);
  const [t, setT] = useState<Template[] | null>(null);
  const [show, setShow] = useState(false);
  useEffect(() => { api<Metrics>("/agents/mensajes/metrics").then(setM).catch(() => null); }, []);
  return (
    <div className="stack" style={{ gap: 8 }}>
      {m && (
        <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))" }} aria-label="Medición de los últimos 7 días">
          {([["Programados", m.programados], ["Enviados", m.por_estado.enviado ?? 0], ["Cancelados", m.por_estado.cancelado ?? 0], ["Con respuesta (3 días)", m.con_respuesta_3_dias], ["Duplicados evitados", m.duplicados_evitados], ["Derivados al equipo", m.derivados_al_equipo]] as const).map(([l, v]) => (
            <div key={l} className="card" style={{ padding: 12 }}><div className="stat" style={{ fontSize: "1.4rem" }}>{v}</div><div className="stat-label">{l}</div></div>
          ))}
        </div>
      )}
      <div className="row"><button className="btn btn-sm" onClick={() => { setShow(!show); if (!t) api<Template[]>("/agents/mensajes/templates").then(setT).catch(() => setT([])); }}>{show ? "Ocultar plantillas" : "Ver plantillas"}</button>
        {m && <span className="small muted">Versión de plantillas {m.plantillas_version} · textos pendientes de validar (T-32)</span>}</div>
      {show && t?.map((x) => (
        <div key={x.code} className="small"><strong>{x.name}</strong> <span className="badge mono">{x.dr}</span><div className="muted" style={{ whiteSpace: "pre-wrap" }}>{x.text}</div></div>
      ))}
    </div>
  );
}

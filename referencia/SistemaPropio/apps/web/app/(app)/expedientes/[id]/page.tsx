"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { useMe } from "@/components/session";
import { CaseEconomy } from "@/components/economy";
import { CommThreadPanel } from "@/components/comm";
import { PendingList } from "@/components/proposals";
import { CaseImmigration } from "@/components/immigration";
import { NewTaskForm, TaskItem } from "@/components/tasks";
import { EstadoBadge, MateriaBadge } from "@/components/ui";
import { api, ApiError, permsIn, type CaseDetail, type CaseMeta, type EligibleUser, type Page, type Task } from "@/lib/api";
import { FASES, fmtDateTime, label } from "@/lib/format";

const NEEDS_NOTE = new Set(["suspendido", "desistido", "resuelto", "archivado", "en_ejecucion"]);
const LEGAL = new Set(["resuelto", "en_ejecucion", "desistido", "archivado"]);

function ExpedienteInner() {
  const { id } = useParams<{ id: string }>();
  const params = useSearchParams();
  const me = useMe();
  const [c, setC] = useState<CaseDetail | null>(null);
  const [denied, setDenied] = useState<ApiError | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [showDone, setShowDone] = useState(false);
  const [newTask, setNewTask] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(params.get("nuevo") ? { ok: true, text: "Expediente abierto en preapertura. La apertura ha quedado registrada." } : null);

  const load = useCallback(() => {
    api<CaseDetail>(`/cases/${id}`).then(setC).catch((e) => setDenied(e instanceof ApiError ? e : null));
    api<Page<Task>>(`/tasks?scope=all&case_id=${id}&open_only=${!showDone}&page_size=100`).then((r) => setTasks(r.items)).catch(() => setTasks([]));
  }, [id, showDone]);
  useEffect(() => { load(); }, [load]);

  if (denied) {
    return (
      <div className="stack">
        <h1>{denied.status === 403 ? "Acceso denegado" : "Expediente no encontrado"}</h1>
        <div className={`notice ${denied.status === 403 ? "notice-danger" : "notice-warn"}`} role="alert">
          <strong>{denied.status === 403 ? "No tiene autorización para este expediente" : "No existe o está fuera de su ámbito"}</strong>
          {denied.message}
          {denied.body.request_id && <div className="small mono">Referencia: {denied.body.request_id}</div>}
        </div>
        <p>Si necesita acceder por una sustitución o una necesidad concreta, solicite a Dirección una autorización puntual.</p>
        <Link href="/expedientes">Volver a expedientes</Link>
      </div>
    );
  }
  if (!c) return <p className="muted">Cargando expediente…</p>;
  const perms = permsIn(me, c.organization_id);

  return (
    <div className="stack">
      <div className="topline">
        <div>
          <p className="small muted" style={{ margin: 0 }}><Link href="/expedientes">Expedientes</Link> / {c.code}</p>
          <h1>{c.title}</h1>
          <div className="row"><MateriaBadge materia={c.materia} /><EstadoBadge status={c.status} /><span className="badge mono">{c.code}</span>
            {c.inactive && <span className="badge badge-red">Sin actividad desde hace {c.inactive_days} días</span>}</div>
        </div>
      </div>
      {msg && <div className={`notice ${msg.ok ? "notice-ok" : "notice-danger"}`} role="status">{msg.text}</div>}
      <div className="notice notice-info small">Su consulta de este expediente ha quedado registrada en la auditoría.</div>

      <div className="grid grid-2">
        <div className="card">
          <h2>Datos</h2>
          <dl className="kv">
            <dt>Cliente</dt><dd><Link href={`/clientes/${c.contact_id}`}>{c.contact_name}</Link></dd>
            <dt>Departamento</dt><dd>{c.department}</dd>
            <dt>Sede</dt><dd>{c.branch}</dd>
            <dt>Alta</dt><dd>{fmtDateTime(c.created_at)}</dd>
            <dt>Encargo confirmado</dt><dd>{c.engagement_confirmed_at ? fmtDateTime(c.engagement_confirmed_at) : "Pendiente"}</dd>
            <dt>Última actividad</dt><dd>{fmtDateTime(c.last_activity_at)}</dd>
            {c.lead_id && <><dt>Origen comercial</dt><dd><Link href={`/crm/${c.lead_id}`}>Ver lead</Link></dd></>}
          </dl>
        </div>
        <PhaseCard c={c} onDone={(t) => { setMsg(t); load(); }} />
      </div>

      <div className="card">
        <h2>Resumen confidencial</h2>
        <p style={{ whiteSpace: "pre-wrap" }}>{c.confidential_summary || <span className="muted">Sin resumen.</span>}</p>
      </div>

      <PendingList params={{ case_id: c.id, kind: "mensaje,dato_falta,invitar_portal" }} hideEmpty title="Pendiente de decidir en este expediente" />
      {perms.includes("comm.read") && <CommThreadPanel caseId={c.id} compact />}

      {(c.materia === "extranjeria" || c.materia === "nacionalidad") && <CaseImmigration caseId={c.id} onChange={load} />}

      <section className="stack" style={{ gap: 10 }}>
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h2 style={{ margin: 0 }}>Tareas</h2>
          <div className="row">
            <label className="row small"><input type="checkbox" style={{ width: "auto" }} checked={showDone} onChange={(e) => setShowDone(e.target.checked)} /> Ver también completadas y anuladas</label>
            {perms.includes("task.create") && <button className="btn btn-sm btn-primary" onClick={() => setNewTask(!newTask)}>{newTask ? "Cerrar" : "+ Tarea"}</button>}
          </div>
        </div>
        {newTask && <NewTaskForm orgId={c.organization_id} caseId={c.id} materia={c.materia} meId={me.id} onCreated={() => { setNewTask(false); load(); }} />}
        {tasks.length === 0 ? <p className="muted">No hay tareas abiertas.</p> : tasks.map((t) => <TaskItem key={t.id} task={t} onChange={load} showCase={false} />)}
      </section>

      {(perms.includes("economy.read.case") || perms.includes("economy.read.all")) && <CaseEconomy caseId={c.id} />}

      <div className="grid grid-2">
        <Assignments c={c} onDone={(t) => { setMsg(t); load(); }} />
        <Relations c={c} onDone={(t) => { setMsg(t); load(); }} />
      </div>

      <div className="card">
        <h2>Historial de fases</h2>
        <table className="data">
          <thead><tr><th>Fecha (Madrid)</th><th>Usuario</th><th>Cambio</th><th>Motivo</th></tr></thead>
          <tbody>{c.phase_events.map((e, i) => (
            <tr key={i}><td>{fmtDateTime(e.at)}</td><td className="mono">{e.actor}</td>
              <td>{e.from ? `${label(FASES, e.from)} → ` : ""}<strong>{label(FASES, e.to)}</strong></td><td>{e.note ?? ""}</td></tr>
          ))}</tbody>
        </table>
      </div>
    </div>
  );
}

function PhaseCard({ c, onDone }: { c: CaseDetail; onDone: (m: { ok: boolean; text: string }) => void }) {
  const [note, setNote] = useState("");
  const [engagement, setEngagement] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  async function go(to: string) {
    setErr(null);
    try {
      await api(`/cases/${c.id}/transition`, { method: "POST", body: JSON.stringify({ to, note: note.trim() || null, engagement_confirmed: engagement }) });
      setNote(""); onDone({ ok: true, text: `Fase cambiada a «${label(FASES, to)}». Queda en el historial; las tareas se conservan.` });
    } catch (e) { setErr(e instanceof ApiError ? e.message : "No se pudo cambiar la fase"); }
  }
  return (
    <div className="card stack">
      <h2 style={{ margin: 0 }}>Fase</h2>
      <div><EstadoBadge status={c.status} /></div>
      {err && <div className="notice notice-danger">{err}</div>}
      {c.status_allowed.length === 0 ? <p className="small muted" style={{ margin: 0 }}>Su perfil no puede cambiar la fase desde «{label(FASES, c.status)}». Las fases con efecto jurídico (resuelto, archivado, desistido, ejecución) solo las cambia un letrado o Dirección.</p> : (
        <>
          {c.status === "preapertura" && c.status_allowed.includes("abierto") && (
            <label className="row small"><input type="checkbox" style={{ width: "auto" }} checked={engagement} onChange={(e) => setEngagement(e.target.checked)} /> Consta el encargo firmado por el cliente</label>
          )}
          <label className="field">Motivo o resultado {c.status_allowed.some((s) => NEEDS_NOTE.has(s)) && <span className="hint">Obligatorio para suspender, resolver, desistir, ejecutar o archivar</span>}
            <textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} /></label>
          <div className="row">{c.status_allowed.map((s) => (
            <button key={s} className={`btn btn-sm ${LEGAL.has(s) ? "btn-warn" : "btn-primary"}`} onClick={() => go(s)}>Pasar a «{label(FASES, s)}»</button>))}</div>
        </>
      )}
    </div>
  );
}

function Assignments({ c, onDone }: { c: CaseDetail; onDone: (m: { ok: boolean; text: string }) => void }) {
  const [users, setUsers] = useState<EligibleUser[]>([]);
  const [f, setF] = useState({ user_id: "", role_in_case: "responsable", reason: "" });
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    if (c.can_assign) api<EligibleUser[]>(`/cases/eligible-users?organization_id=${c.organization_id}&materia=${c.materia}`).then(setUsers).catch(() => setUsers([]));
  }, [c.can_assign, c.materia, c.organization_id]);
  const active = c.assignments.filter((a) => !a.until);
  async function add() {
    setErr(null);
    try { await api(`/cases/${c.id}/assignments`, { method: "POST", body: JSON.stringify(f) }); setF({ user_id: "", role_in_case: "responsable", reason: "" }); onDone({ ok: true, text: "Asignación registrada." }); }
    catch (e) { setErr(e instanceof ApiError ? e.message : "Error"); }
  }
  async function end(aid: string) {
    try { await api(`/cases/${c.id}/assignments/${aid}/end`, { method: "POST" }); onDone({ ok: true, text: "Asignación finalizada." }); }
    catch (e) { setErr(e instanceof ApiError ? e.message : "Error"); }
  }
  return (
    <div className="card stack">
      <h2 style={{ margin: 0 }}>Responsables</h2>
      <ul style={{ margin: 0, paddingLeft: 18 }}>{active.map((a) => (
        <li key={a.id}>{a.user} · {a.role} desde {fmtDateTime(a.since)} {c.can_assign && <button className="link small" style={{ marginLeft: 6 }} onClick={() => end(a.id)}>Retirar</button>}</li>))}</ul>
      {c.assignments.some((a) => a.until) && <details><summary className="small">Anteriores</summary><ul className="small">{c.assignments.filter((a) => a.until).map((a) => <li key={a.id}>{a.user} · {a.role} · {fmtDateTime(a.since)} → {fmtDateTime(a.until)}</li>)}</ul></details>}
      {err && <div className="notice notice-danger">{err}</div>}
      {c.can_assign && (
        <div className="form-grid">
          <label className="field">Persona<select value={f.user_id} onChange={(e) => setF({ ...f, user_id: e.target.value })}><option value="">Elija…</option>{users.map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}</select></label>
          <label className="field">Papel<select value={f.role_in_case} onChange={(e) => setF({ ...f, role_in_case: e.target.value })}><option value="responsable">Responsable (sustituye al actual)</option><option value="letrado">Letrado</option><option value="gestor">Gestor</option><option value="apoyo">Apoyo</option></select></label>
          <label className="field full">Motivo *<input value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })} /></label>
          <div className="full"><button className="btn btn-sm btn-primary" disabled={!f.user_id} onClick={add}>Asignar</button></div>
          <p className="full small muted" style={{ margin: 0 }}>Solo aparecen personas de esta rama. Para una excepción entre ramas use una autorización puntual (Ajustes).</p>
        </div>
      )}
    </div>
  );
}

function Relations({ c, onDone }: { c: CaseDetail; onDone: (m: { ok: boolean; text: string }) => void }) {
  const [others, setOthers] = useState<CaseMeta[]>([]);
  const [f, setF] = useState({ related_case_id: "", kind: "mismo_cliente" });
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    api<CaseMeta[]>(`/contacts/${c.contact_id}/cases`).then((r) => setOthers(r.filter((x) => x.id !== c.id && x.access_level === "full" && !c.relations.some((y) => y.id === x.id)))).catch(() => undefined);
  }, [c]);
  async function add() {
    setErr(null);
    try { await api(`/cases/${c.id}/relations`, { method: "POST", body: JSON.stringify(f) }); onDone({ ok: true, text: "Expedientes relacionados." }); }
    catch (e) { setErr(e instanceof ApiError ? e.message : "Error"); }
  }
  return (
    <div className="card stack">
      <h2 style={{ margin: 0 }}>Expedientes relacionados</h2>
      {c.relations.length === 0 ? <p className="small muted" style={{ margin: 0 }}>Ninguno visible para usted.</p> : (
        <ul style={{ margin: 0, paddingLeft: 18 }}>{c.relations.map((r) => <li key={r.id}>{r.access_level === "full" ? <Link href={`/expedientes/${r.id}`}>{r.code}</Link> : r.code} · {r.kind.replace("_", " ")}</li>)}</ul>
      )}
      {err && <div className="notice notice-danger">{err}</div>}
      {others.length > 0 && (
        <div className="row">
          <select style={{ flex: 1, minWidth: 160 }} value={f.related_case_id} onChange={(e) => setF({ ...f, related_case_id: e.target.value })} aria-label="Expediente a relacionar">
            <option value="">Otro expediente del mismo cliente…</option>{others.map((o) => <option key={o.id} value={o.id}>{o.code} · {o.materia}</option>)}</select>
          <select style={{ width: "auto" }} value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value })} aria-label="Tipo de relación"><option value="mismo_cliente">Mismo cliente</option><option value="conexo">Conexo</option><option value="derivado">Derivado</option></select>
          <button className="btn btn-sm" disabled={!f.related_case_id} onClick={add}>Relacionar</button>
        </div>
      )}
    </div>
  );
}

export default function ExpedientePage() {
  return <Suspense fallback={<p className="muted">Cargando…</p>}><ExpedienteInner /></Suspense>;
}

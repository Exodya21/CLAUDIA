"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { KindBadge, LegalBadge, TaskStatusBadge } from "@/components/ui";
import { api, ApiError, fieldErrors, type EligibleUser, type Task, type TaskDetail } from "@/lib/api";
import { ACCION_TAREA, fmtDateTime, fmtTime, fromLocalInput, label, TAREA_TIPOS, toLocalInput } from "@/lib/format";

/** Una tarea en lista, desplegable con sus acciones e historial. */
export function TaskItem({ task, onChange, showCase = true }: { task: Task; onChange: () => void; showCase?: boolean }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="card" style={{ padding: "12px 16px", borderLeft: task.overdue ? "4px solid var(--danger)" : undefined }}>
      <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div className="row" style={{ gap: 6 }}>
            <KindBadge kind={task.kind} /><TaskStatusBadge s={task.status} />
            {task.priority === "alta" && <span className="badge badge-red">Prioridad alta</span>}
            {task.overdue && <span className="badge badge-red">Vencida</span>}
            {task.overlaps.length > 0 && <span className="badge badge-yellow" title="Coincide en horario con otra tarea de la misma persona">Solapa con otra cita</span>}
            <LegalBadge status={task.legal_status} date={task.legal_deadline} />
          </div>
          <div style={{ fontWeight: 600, marginTop: 6 }}>{task.title}</div>
          <div className="small muted">
            {task.start_at ? `${fmtDateTime(task.start_at)}–${fmtTime(task.end_at)}` : `Fecha interna: ${fmtDateTime(task.due_at)}`}
            {" · "}<span className="mono">{task.assignee}</span>
            {showCase && task.case_code && <> · {task.case_id ? <Link href={`/expedientes/${task.case_id}`}>{task.case_code}</Link> : task.case_code}{task.contact_name ? ` (${task.contact_name})` : ""}</>}
            {task.location && <> · {task.location}</>}
          </div>
        </div>
        <button className="btn btn-sm" onClick={() => setOpen(!open)} aria-expanded={open}>{open ? "Cerrar" : "Gestionar"}</button>
      </div>
      {open && <TaskPanel id={task.id} onChange={onChange} />}
    </div>
  );
}

function TaskPanel({ id, onChange }: { id: string; onChange: () => void }) {
  const [t, setT] = useState<TaskDetail | null>(null);
  const [mode, setMode] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [due, setDue] = useState("");
  const [legal, setLegal] = useState({ date: "", source: "" });
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const load = () => api<TaskDetail>(`/tasks/${id}`).then(setT).catch(() => undefined);
  useEffect(() => { load(); }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  async function call(path: string, body: object, ok: string) {
    setMsg(null);
    try {
      await api(path, { method: "POST", body: JSON.stringify(body) });
      setMsg({ ok: true, text: ok }); setMode(null); setReason(""); await load(); onChange();
    } catch (e) {
      const fe = fieldErrors(e);
      setMsg({ ok: false, text: (e instanceof ApiError ? e.message : "Error") + (Object.keys(fe).length ? ` (${Object.values(fe).join(", ")})` : "") });
    }
  }
  if (!t) return <p className="muted small" style={{ marginTop: 10 }}>Cargando…</p>;

  const transition = (to: string) => {
    if (to === "pospuesta" || to === "anulada") { setMode(to); if (to === "pospuesta") setDue(toLocalInput(new Date(Date.now() + 3 * 864e5))); return; }
    call(`/tasks/${t.id}/transition`, { to, version: t.version }, "Tarea actualizada.");
  };

  return (
    <div className="stack" style={{ marginTop: 12, gap: 12, borderTop: "1px solid var(--line)", paddingTop: 12 }}>
      {msg && <div className={`notice ${msg.ok ? "notice-ok" : "notice-danger"}`}>{msg.text}</div>}
      {t.description && <p className="small" style={{ margin: 0 }}>{t.description}</p>}

      <div className="grid grid-2">
        <div>
          <h3>Fecha interna</h3>
          <p className="small" style={{ margin: 0 }}>{fmtDateTime(t.due_at)} <span className="muted">(objetivo del despacho)</span></p>
        </div>
        <div>
          <h3>Plazo legal</h3>
          {t.legal_status === "no_aplica" ? <p className="small muted" style={{ margin: 0 }}>No consta.</p> : (
            <p className="small" style={{ margin: 0 }}>
              <LegalBadge status={t.legal_status} date={t.legal_deadline} /><br />
              Fuente: {t.legal_source}
              {t.legal_validated_by && <><br />Validado por <span className="mono">{t.legal_validated_by}</span> el {fmtDateTime(t.legal_validated_at)}</>}
            </p>
          )}
        </div>
      </div>

      {t.can_edit && t.allowed_transitions.length > 0 && !mode && (
        <div className="row">
          {t.allowed_transitions.map((to) => <button key={to} className={`btn btn-sm ${to === "completada" ? "btn-primary" : ""}`} onClick={() => transition(to)}>{label(ACCION_TAREA, to)}</button>)}
          {t.case_id && (t.kind === "conciliacion" || t.kind === "senalamiento") && <button className="btn btn-sm" onClick={() => { setMode("lugar"); setReason(t.location ?? ""); }}>{t.location ? "Corregir lugar" : "Indicar lugar"}</button>}
          {t.case_id && <button className="btn btn-sm" onClick={() => { setMode("legal"); setLegal({ date: t.legal_deadline ?? "", source: t.legal_source ?? "" }); }}>{t.legal_status === "no_aplica" ? "Proponer plazo legal" : "Corregir plazo legal"}</button>}
        </div>
      )}
      {!t.can_edit && <p className="small muted" style={{ margin: 0 }}>Solo la persona asignada, quien la creó o un responsable del área pueden modificar esta tarea.</p>}

      {mode === "pospuesta" && (
        <div className="form-grid">
          <label className="field">Nueva fecha *<input type="datetime-local" value={due} onChange={(e) => setDue(e.target.value)} /></label>
          <label className="field">Motivo del aplazamiento *<input value={reason} onChange={(e) => setReason(e.target.value)} /></label>
          <div className="full row">
            <button className="btn btn-warn btn-sm" onClick={() => call(`/tasks/${t.id}/transition`, { to: "pospuesta", version: t.version, reason, new_due_at: due ? fromLocalInput(due) : null }, "Tarea aplazada. La fecha anterior queda en el historial.")}>Aplazar</button>
            <button className="btn btn-sm" onClick={() => setMode(null)}>Cancelar</button>
          </div>
        </div>
      )}
      {mode === "lugar" && (
        <div className="row">
          <input style={{ flex: 1, minWidth: 200 }} aria-label="Lugar" placeholder="Juzgado, sala, servicio de conciliación… *" value={reason} onChange={(e) => setReason(e.target.value)} />
          <button className="btn btn-sm btn-primary" onClick={() => call(`/tasks/${t.id}/location`, { version: t.version, location: reason }, "Lugar guardado. El aviso al cliente se preparará con este dato.")}>Guardar lugar</button>
          <button className="btn btn-sm" onClick={() => setMode(null)}>Cancelar</button>
        </div>
      )}
      {mode === "anulada" && (
        <div className="row">
          <input style={{ flex: 1, minWidth: 200 }} placeholder="Motivo de la anulación *" value={reason} onChange={(e) => setReason(e.target.value)} />
          <button className="btn btn-sm" onClick={() => call(`/tasks/${t.id}/transition`, { to: "anulada", version: t.version, reason }, "Tarea anulada.")}>Anular</button>
          <button className="btn btn-sm" onClick={() => setMode(null)}>Cancelar</button>
        </div>
      )}
      {mode === "legal" && (
        <div className="form-grid">
          <label className="field">Fecha legal propuesta *<input type="date" value={legal.date} onChange={(e) => setLegal({ ...legal, date: e.target.value })} /></label>
          <label className="field">Fuente * <span className="hint">Resolución, diligencia o notificación de la que sale</span><input value={legal.source} onChange={(e) => setLegal({ ...legal, source: e.target.value })} /></label>
          <p className="full small muted" style={{ margin: 0 }}>El sistema no calcula plazos: esta fecha quedará SIN VALIDAR hasta que otro letrado la confirme.</p>
          <div className="full row">
            <button className="btn btn-sm btn-primary" onClick={() => call(`/tasks/${t.id}/legal-deadline`, { version: t.version, legal_deadline: legal.date, legal_source: legal.source }, "Plazo propuesto. Pendiente de validación letrada.")}>Proponer</button>
            <button className="btn btn-sm" onClick={() => setMode(null)}>Cancelar</button>
          </div>
        </div>
      )}
      {t.can_validate_legal && !mode && (
        <div className="notice notice-warn">
          <strong>Validación letrada pendiente</strong>
          Compruebe la fecha {t.legal_deadline?.split("-").reverse().join("/")} con su fuente antes de validarla.
          <div className="row" style={{ marginTop: 8 }}>
            <button className="btn btn-sm btn-primary" onClick={() => call(`/tasks/${t.id}/legal-deadline/decision`, { version: t.version, decision: "validar" }, "Plazo legal validado.")}>Validar plazo</button>
            <input style={{ flex: 1, minWidth: 180 }} placeholder="Motivo si la rechaza" value={reason} onChange={(e) => setReason(e.target.value)} />
            <button className="btn btn-sm" onClick={() => call(`/tasks/${t.id}/legal-deadline/decision`, { version: t.version, decision: "rechazar", note: reason }, "Plazo rechazado.")}>Rechazar</button>
          </div>
        </div>
      )}

      <details>
        <summary className="small" style={{ cursor: "pointer" }}>Historial ({t.events.length})</summary>
        <table className="data" style={{ marginTop: 8 }}>
          <tbody>{t.events.map((e, i) => (
            <tr key={i}><td className="small" style={{ whiteSpace: "nowrap" }}>{fmtDateTime(e.at)}</td><td className="mono small">{e.actor}</td>
              <td className="small">{e.kind.replaceAll("_", " ")}{e.to ? ` → ${e.to}` : ""}
                {e.old_due_at && <div>Fecha anterior: {fmtDateTime(e.old_due_at)} → nueva: {fmtDateTime(e.new_due_at)}</div>}
                {e.reason && <div className="muted">{e.reason}</div>}</td></tr>
          ))}</tbody>
        </table>
      </details>
    </div>
  );
}

/** Alta de tarea, dentro de un expediente o personal. */
export function NewTaskForm({ orgId, caseId, materia, meId, onCreated }: { orgId: string; caseId?: string; materia?: string; meId: string; onCreated: () => void }) {
  const [users, setUsers] = useState<EligibleUser[]>([]);
  const [f, setF] = useState({ title: "", kind: "gestion", priority: "media", assignee_id: meId, due: toLocalInput(new Date(Date.now() + 864e5)),
    start: "", end: "", location: "", description: "", legal_date: "", legal_source: "" });
  const [msg, setMsg] = useState<string | null>(null);
  const [errs, setErrs] = useState<Record<string, string>>({});
  useEffect(() => {
    if (caseId && materia) api<EligibleUser[]>(`/cases/eligible-users?organization_id=${orgId}&materia=${materia}`).then(setUsers).catch(() => setUsers([]));
  }, [orgId, caseId, materia]);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setF((s) => ({ ...s, [k]: e.target.value }));
  const timed = f.kind === "senalamiento" || f.kind === "conciliacion";

  async function save() {
    setMsg(null); setErrs({});
    const body: Record<string, unknown> = {
      organization_id: orgId, case_id: caseId ?? null, title: f.title, kind: f.kind, priority: f.priority, assignee_id: f.assignee_id,
      description: f.description, location: f.location || null,
      due_at: fromLocalInput(timed && f.start ? f.start : f.due),
      start_at: timed && f.start ? fromLocalInput(f.start) : null, end_at: timed && f.end ? fromLocalInput(f.end) : null,
      legal_deadline: f.legal_date || null, legal_source: f.legal_source || null,
    };
    try { await api("/tasks", { method: "POST", body: JSON.stringify(body) }); onCreated(); }
    catch (e) { setMsg(e instanceof ApiError ? e.message : "No se pudo crear"); setErrs(fieldErrors(e)); }
  }

  return (
    <div className="card stack">
      <h2 style={{ margin: 0 }}>Nueva tarea</h2>
      {msg && <div className="notice notice-danger">{msg}{Object.keys(errs).length > 0 && <div className="small">{Object.values(errs).join(" · ")}</div>}</div>}
      <div className="form-grid">
        <label className="field full">Qué hay que hacer *<input value={f.title} onChange={set("title")} /></label>
        <label className="field">Tipo<select value={f.kind} onChange={set("kind")}>{Object.entries(TAREA_TIPOS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
        <label className="field">Prioridad<select value={f.priority} onChange={set("priority")}><option value="alta">Alta</option><option value="media">Media</option><option value="baja">Baja</option></select></label>
        {caseId ? (
          <label className="field">Responsable<select value={f.assignee_id} onChange={set("assignee_id")}>
            {!users.some((u) => u.id === meId) && <option value={meId}>Yo</option>}
            {users.map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}</select></label>
        ) : <p className="small muted">Tarea personal (sin expediente): se asigna a usted.</p>}
        {timed ? (
          <>
            <label className="field">Inicio *<input type="datetime-local" value={f.start} onChange={set("start")} /></label>
            <label className="field">Fin *<input type="datetime-local" value={f.end} onChange={set("end")} /></label>
            <label className="field full">Lugar<input value={f.location} onChange={set("location")} placeholder="Juzgado, sala, servicio de conciliación…" /></label>
          </>
        ) : (
          <label className="field">Fecha interna (objetivo del despacho)<input type="datetime-local" value={f.due} onChange={set("due")} /></label>
        )}
        {caseId && (
          <>
            <label className="field">Plazo legal (opcional) <span className="hint">Quedará SIN VALIDAR hasta que lo confirme otro letrado</span><input type="date" value={f.legal_date} onChange={set("legal_date")} /></label>
            {f.legal_date && <label className="field">Fuente del plazo *<input value={f.legal_source} onChange={set("legal_source")} placeholder="Diligencia de …, notificación de …" /></label>}
          </>
        )}
        <label className="field full">Detalle<textarea rows={2} value={f.description} onChange={set("description")} /></label>
      </div>
      <div className="row"><button className="btn btn-primary" onClick={save}>Crear tarea</button></div>
    </div>
  );
}

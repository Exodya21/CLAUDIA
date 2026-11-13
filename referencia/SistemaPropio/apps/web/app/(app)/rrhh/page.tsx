"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { MoneyInput } from "@/components/economy";
import { PendingList } from "@/components/proposals";
import { useMe } from "@/components/session";
import { api, ApiError, fieldErrors, hasPerm, postForm } from "@/lib/api";
import { fmtDate, fmtDateTime, fmtMoney, parseMoney } from "@/lib/format";

interface Doc { id: string; kind: string; kind_label: string; period: string | null; name: string; status: string; extracted: Record<string, unknown> | null; confirmed: Record<string, number | string> | null; uploaded_at: string; uploaded_by: string; version: number; can_review: boolean }
interface Leave { id: string; employee_id: string; employee: string; kind: string; kind_label: string; start_date: string; end_date: string; working_days: number; note: string | null; status: string; requested_by: string; decided_by: string | null; decision_note: string | null; version: number; can_decide?: boolean; coincidencias?: number | Leave[]; branch?: string }
interface Emp {
  id: string; organization_id: string; organization: string; code: string; name: string; branch: string; branch_id: string; department: string | null; department_id: string | null;
  country: string; category: string; job_title: string; contract_type: string; workday: string; weekly_hours: number; start_date: string;
  contract_end_date: string | null; trial_end_date: string | null; status: string; version: number; is_me: boolean;
  email?: string | null; phone?: string | null; national_id_masked?: string | null; vacation_days_year?: number | null; notes?: string | null;
  salary_annual_cents?: number | null; can: { manage: boolean; salary: boolean; leave_decide: boolean };
  vacation?: { year: number; total: number | null; used: number; pending: number; remaining: number | null }; documents?: Doc[]; leaves?: Leave[];
}
const CONTRATOS: Record<string, string> = { indefinido: "Indefinido", temporal: "Temporal", practicas: "Prácticas", fijo_discontinuo: "Fijo discontinuo", otro: "Otro" };
const ESTADOS: Record<string, string> = { activo: "Activo", baja: "De baja", excedencia: "Excedencia", finalizado: "Finalizado" };
const LEAVE_ST: Record<string, string> = { solicitada: "badge-yellow", aprobada: "badge-green", rechazada: "badge-red", anulada: "" };
const errMsg = (e: unknown) => (e instanceof ApiError ? e.message : "No se ha podido completar la operación.");
const curOf = (e: Emp) => (e.country === "CO" ? "COP" : "EUR");
type Tab = "mi" | "plantilla" | "ausencias" | "nominas" | "importar" | "avisos";

function Rrhh() {
  const me = useMe();
  const params = useSearchParams();
  const canRead = hasPerm(me, "hr.read");
  const canDecide = hasPerm(me, "hr.leave.decide");
  const canSalary = hasPerm(me, "hr.salary");
  const canManage = hasPerm(me, "hr.manage");
  const tabs: [Tab, string, boolean][] = [
    ["mi", "Mi ficha", hasPerm(me, "hr.self")], ["plantilla", canRead ? "Plantilla" : "Mi equipo", canRead || canDecide],
    ["ausencias", "Ausencias", canRead || canDecide], ["nominas", "Nóminas", canSalary],
    ["importar", "Importar", canManage && canSalary], ["avisos", "Avisos", canManage || canSalary],
  ];
  const visible = tabs.filter((t) => t[2]);
  const [tab, setTab] = useState<Tab>(params.get("tab") === "pendientes" && (canManage || canSalary) ? "avisos" : (visible.find((t) => t[0] !== "mi")?.[0] ?? "mi"));
  const [alerts, setAlerts] = useState<number | null>(null);
  if (!visible.length) return <div className="notice notice-warn"><strong>Sin acceso</strong>Su perfil no tiene funciones de RRHH.</div>;
  return (
    <div className="stack">
      <div className="topline">
        <div>
          <h1>Recursos Humanos</h1>
          <p className="subtitle">Ficha única de cada persona, carpeta de documentos, vacaciones y ausencias, vencimientos y resumen de nóminas para la gestoría. Los datos del personal están separados de los de clientes; salarios y bajas tienen acceso restringido. El sistema no calcula nóminas.</p>
        </div>
      </div>
      <div className="tabs" role="tablist">
        {visible.map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}>{l}{k === "avisos" && alerts ? ` (${alerts})` : ""}</button>)}
      </div>
      {tab === "mi" && <MyFile />}
      {tab === "plantilla" && <Staff />}
      {tab === "ausencias" && <Leaves />}
      {tab === "nominas" && <Payroll />}
      {tab === "importar" && <Import />}
      {(canManage || canSalary) && <div hidden={tab !== "avisos"}>
        <PendingList params={{ agent: "rrhh" }} decided onCount={setAlerts} empty="No hay avisos de plantilla." />
        <p className="small muted">Aprobar un aviso crea una tarea en su agenda para esa fecha. El sistema no renueva contratos ni aprueba nada por su cuenta.</p>
      </div>}
    </div>
  );
}

// ------------------------------------------------------------------ mi ficha
function MyFile() {
  const [e, setE] = useState<Emp | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const load = useCallback(() => api<Emp>("/hr/me").then(setE).catch((x) => setErr(errMsg(x))), []);
  useEffect(() => { load(); }, [load]);
  if (err) return <div className="notice notice-info">{err}</div>;
  if (!e) return <p className="muted">Cargando…</p>;
  return <EmployeeDetail e={e} onChanged={load} />;
}

function EmployeeDetail({ e, onChanged }: { e: Emp; onChanged: () => void }) {
  const [editing, setEditing] = useState(false);
  return (
    <div className="stack" aria-label={`Ficha de ${e.name}`}>
      <div className="card">
        <div className="row"><h2 style={{ margin: 0 }}>{e.name}</h2><span className="badge mono">{e.code}</span><span className={`badge ${e.status === "activo" ? "badge-green" : "badge-yellow"}`}>{ESTADOS[e.status]}</span>
          <span className="spacer" />{e.can.manage && <button className="btn btn-sm" onClick={() => setEditing(!editing)}>{editing ? "Cerrar" : "Modificar ficha"}</button>}</div>
        <dl className="kv" style={{ marginTop: 10 }}>
          <dt>Entidad y sede</dt><dd>{e.organization} · {e.branch}{e.department ? ` · ${e.department}` : ""}</dd>
          <dt>Puesto</dt><dd>{e.job_title} ({e.category})</dd>
          <dt>Contrato</dt><dd>{CONTRATOS[e.contract_type]} · jornada {e.workday} ({e.weekly_hours} h/semana)</dd>
          <dt>Antigüedad</dt><dd>{fmtDate(e.start_date)}</dd>
          {e.contract_end_date && <><dt>Fin de contrato</dt><dd>{fmtDate(e.contract_end_date)}</dd></>}
          {e.trial_end_date && <><dt>Fin del periodo de prueba</dt><dd>{fmtDate(e.trial_end_date)}</dd></>}
          {e.salary_annual_cents !== undefined && <><dt>Salario bruto anual</dt><dd>{fmtMoney(e.salary_annual_cents, curOf(e))}</dd></>}
          {e.national_id_masked && <><dt>Documento</dt><dd className="mono">{e.national_id_masked}</dd></>}
          {e.email && <><dt>Correo</dt><dd>{e.email}</dd></>}
        </dl>
        {editing && <EditEmployee e={e} onDone={() => { setEditing(false); onChanged(); }} />}
      </div>
      {e.vacation && (
        <div className="card">
          <h2>Vacaciones {e.vacation.year}</h2>
          {e.vacation.total === null ? <p className="small muted">Los días de vacaciones de esta persona no están informados (según su convenio, T-50).</p> : (
            <div className="row"><span className="stat" style={{ fontSize: "1.6rem" }}>{e.vacation.remaining}</span><span className="small">días laborables disponibles de {e.vacation.total} · {e.vacation.used} disfrutados o aprobados · {e.vacation.pending} pendientes de aprobar</span></div>
          )}
          {(e.is_me || e.can.manage) && <LeaveForm e={e} onDone={onChanged} />}
          <LeaveTable rows={e.leaves ?? []} onChanged={onChanged} />
        </div>
      )}
      <Documents e={e} onChanged={onChanged} />
    </div>
  );
}

function EditEmployee({ e, onDone }: { e: Emp; onDone: () => void }) {
  const [f, setF] = useState({ job_title: e.job_title, category: e.category, contract_type: e.contract_type, contract_end_date: e.contract_end_date ?? "", trial_end_date: e.trial_end_date ?? "", status: e.status, vacation_days_year: e.vacation_days_year?.toString() ?? "", salary: e.salary_annual_cents != null ? (e.salary_annual_cents / 100).toFixed(2).replace(".", ",") : "", reason: "" });
  const [err, setErr] = useState<string | null>(null);
  const set = (k: keyof typeof f) => (x: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [k]: x.target.value });
  async function save(ev: React.FormEvent) {
    ev.preventDefault(); setErr(null);
    const body: Record<string, unknown> = { version: e.version, reason: f.reason, job_title: f.job_title, category: f.category, contract_type: f.contract_type, status: f.status };
    const clear: string[] = [];
    if (f.contract_end_date) body.contract_end_date = f.contract_end_date; else if (e.contract_end_date) clear.push("contract_end_date");
    if (f.trial_end_date) body.trial_end_date = f.trial_end_date; else if (e.trial_end_date) clear.push("trial_end_date");
    if (f.vacation_days_year) body.vacation_days_year = Number(f.vacation_days_year);
    if (e.can.salary && f.salary) { const c = parseMoney(f.salary); if (c === null) { setErr("Salario no válido"); return; } if (c !== e.salary_annual_cents) body.salary_annual_cents = c; }
    body.clear = clear;
    try { await api(`/hr/employees/${e.id}`, { method: "PATCH", body: JSON.stringify(body) }); onDone(); }
    catch (x) { setErr(errMsg(x) + (Object.keys(fieldErrors(x)).length ? ` (${Object.values(fieldErrors(x)).join(", ")})` : "")); }
  }
  return (
    <form className="form-grid" style={{ marginTop: 12 }} onSubmit={save} aria-label="Modificar ficha">
      <label className="field">Puesto<input value={f.job_title} onChange={set("job_title")} /></label>
      <label className="field">Categoría<input value={f.category} onChange={set("category")} /></label>
      <label className="field">Contrato<select value={f.contract_type} onChange={set("contract_type")}>{Object.entries(CONTRATOS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
      <label className="field">Situación<select value={f.status} onChange={set("status")}>{Object.entries(ESTADOS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
      <label className="field">Fin de contrato<input type="date" value={f.contract_end_date} onChange={set("contract_end_date")} /></label>
      <label className="field">Fin del periodo de prueba<input type="date" value={f.trial_end_date} onChange={set("trial_end_date")} /></label>
      <label className="field">Días de vacaciones al año (convenio)<input inputMode="numeric" value={f.vacation_days_year} onChange={set("vacation_days_year")} /></label>
      {e.can.salary && <MoneyInput label="Salario bruto anual" value={f.salary} onChange={(v) => setF({ ...f, salary: v })} />}
      <label className="field full">Motivo del cambio *<input value={f.reason} onChange={set("reason")} minLength={5} required /></label>
      {err && <div className="full notice notice-danger">{err}</div>}
      <div className="full"><button className="btn btn-primary">Guardar cambios</button></div>
    </form>
  );
}

function LeaveForm({ e, onDone }: { e: Emp; onDone: () => void }) {
  const [f, setF] = useState({ kind: "vacaciones", start: "", end: "", note: "" });
  const [err, setErr] = useState<string | null>(null);
  const [warn, setWarn] = useState<Leave[] | null>(null);
  async function send(ev: React.FormEvent) {
    ev.preventDefault(); setErr(null); setWarn(null);
    try {
      const r = await api<Leave>(`/hr/employees/${e.id}/leaves`, { method: "POST", body: JSON.stringify({ kind: f.kind, start_date: f.start, end_date: f.end, note: f.note || null }) });
      if (Array.isArray(r.coincidencias) && r.coincidencias.length) setWarn(r.coincidencias);
      setF({ kind: "vacaciones", start: "", end: "", note: "" }); onDone();
    } catch (x) { setErr(errMsg(x)); }
  }
  return (
    <form className="row" style={{ margin: "12px 0" }} onSubmit={send} aria-label="Pedir ausencia">
      <select aria-label="Tipo de ausencia" value={f.kind} onChange={(x) => setF({ ...f, kind: x.target.value })} style={{ width: "auto" }}>
        <option value="vacaciones">Vacaciones</option><option value="asuntos_propios">Asuntos propios</option><option value="permiso">Permiso</option>
        {e.can.manage && <option value="baja">Baja médica (RRHH)</option>}<option value="otro">Otro</option>
      </select>
      <input type="date" aria-label="Desde" value={f.start} onChange={(x) => setF({ ...f, start: x.target.value })} required style={{ width: "auto" }} />
      <input type="date" aria-label="Hasta" value={f.end} onChange={(x) => setF({ ...f, end: x.target.value })} required style={{ width: "auto" }} />
      <input aria-label="Comentario" placeholder="Comentario (opcional)" value={f.note} onChange={(x) => setF({ ...f, note: x.target.value })} style={{ maxWidth: 260 }} />
      <button className="btn btn-primary btn-sm">{e.is_me ? "Pedir" : "Registrar"}</button>
      {err && <span className="error-text small" role="alert">{err}</span>}
      {warn && <div className="notice notice-warn small" style={{ width: "100%" }}><strong>Solicitado. Coincide con otras ausencias del mismo equipo:</strong>{warn.map((w) => `${w.employee} (${fmtDate(w.start_date)}–${fmtDate(w.end_date)})`).join(" · ")}</div>}
    </form>
  );
}

function LeaveTable({ rows, onChanged, queue = false }: { rows: Leave[]; onChanged: () => void; queue?: boolean }) {
  const [note, setNote] = useState<Record<string, string>>({});
  const [err, setErr] = useState<string | null>(null);
  async function decide(x: Leave, approve: boolean) {
    setErr(null);
    try { await api(`/hr/leaves/${x.id}/decide`, { method: "POST", body: JSON.stringify({ version: x.version, approve, note: note[x.id] || null }) }); onChanged(); }
    catch (e) { setErr(errMsg(e)); }
  }
  return (
    <div className="table-wrap">
      {err && <div className="notice notice-danger" role="alert">{err}</div>}
      <table className="data">
        <thead><tr>{queue && <th>Persona</th>}<th>Tipo</th><th>Fechas</th><th>Días</th><th>Estado</th>{queue && <th></th>}</tr></thead>
        <tbody>
          {rows.length === 0 && <tr><td colSpan={queue ? 6 : 4} className="empty">{queue ? "No hay solicitudes pendientes." : "Sin ausencias registradas."}</td></tr>}
          {rows.map((x) => (
            <tr key={x.id}>
              {queue && <td>{x.employee}<div className="small muted">{x.branch}</div></td>}
              <td>{x.kind_label}{x.note ? <div className="small muted">{x.note}</div> : null}</td>
              <td>{fmtDate(x.start_date)} – {fmtDate(x.end_date)}{queue && typeof x.coincidencias === "number" && x.coincidencias > 0 && <div><span className="badge badge-yellow">coincide con {x.coincidencias} del equipo</span></div>}</td>
              <td>{x.working_days}</td>
              <td><span className={`badge ${LEAVE_ST[x.status] ?? ""}`}>{x.status}</span>{x.decided_by && <div className="small muted">{x.decided_by}{x.decision_note ? `: ${x.decision_note}` : ""}</div>}</td>
              {queue && <td>{x.can_decide ? (
                <div className="row" style={{ gap: 4 }}>
                  <button className="btn btn-sm btn-primary" onClick={() => decide(x, true)}>Aprobar</button>
                  <input aria-label={`Motivo para ${x.employee}`} placeholder="Motivo si rechaza" value={note[x.id] ?? ""} onChange={(e) => setNote({ ...note, [x.id]: e.target.value })} style={{ width: 150 }} />
                  <button className="btn btn-sm" onClick={() => decide(x, false)}>Rechazar</button>
                </div>) : <span className="small muted">{x.status === "solicitada" ? "La decide su responsable" : ""}</span>}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Documents({ e, onChanged }: { e: Emp; onChanged: () => void }) {
  const [kind, setKind] = useState("nomina");
  const [file, setFile] = useState<File | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [rev, setRev] = useState<string | null>(null);
  async function upload(ev: React.FormEvent) {
    ev.preventDefault(); setErr(null);
    const fd = new FormData(); fd.append("kind", kind); fd.append("file", file!);
    try { const d = await postForm<Doc>(`/hr/employees/${e.id}/documents`, fd); setFile(null); onChanged(); if (d.kind === "nomina") setRev(d.id); }
    catch (x) { setErr(errMsg(x)); }
  }
  const docs = e.documents ?? [];
  return (
    <div className="card">
      <h2>Carpeta de documentos</h2>
      {e.can.manage && (
        <form className="row" onSubmit={upload} aria-label="Subir documento">
          <select aria-label="Tipo de documento" value={kind} onChange={(x) => setKind(x.target.value)} style={{ width: "auto" }}>
            {[["nomina", "Nómina"], ["contrato", "Contrato"], ["anexo", "Anexo"], ["certificado", "Certificado"], ["solicitud", "Solicitud"], ["baja", "Parte de baja"], ["otro", "Otro"]]
              .filter(([k]) => k !== "nomina" || e.can.salary).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <input type="file" aria-label="Archivo" accept=".pdf,.jpg,.jpeg,.png" onChange={(x) => setFile(x.target.files?.[0] ?? null)} style={{ maxWidth: 320 }} />
          <button className="btn btn-sm btn-primary" disabled={!file}>Subir</button>
          {err && <span className="error-text small" role="alert">{err}</span>}
        </form>
      )}
      <div className="table-wrap" style={{ marginTop: 10 }}>
        <table className="data">
          <thead><tr><th>Tipo</th><th>Periodo</th><th>Archivo</th><th>Estado</th><th></th></tr></thead>
          <tbody>
            {docs.length === 0 && <tr><td colSpan={5} className="empty">Carpeta vacía.</td></tr>}
            {docs.map((d) => (
              <tr key={d.id}>
                <td>{d.kind_label}</td><td>{d.period ?? "—"}</td>
                <td><a href={`/api/v1/hr/documents/${d.id}/file`} target="_blank" rel="noreferrer">{d.name}</a><div className="small muted">{fmtDateTime(d.uploaded_at)} · {d.uploaded_by}</div></td>
                <td><span className={`badge ${d.status === "valido" ? "badge-green" : d.status === "rechazado" ? "badge-red" : "badge-yellow"}`}>{d.status === "valido" ? "Confirmado" : d.status === "rechazado" ? "No válido" : "Por revisar"}</span>
                  {d.confirmed?.liquido_cents !== undefined && <div className="small">Líquido {fmtMoney(Number(d.confirmed.liquido_cents), curOf(e))}</div>}</td>
                <td>{d.can_review && d.status === "pendiente_revision" && <button className="btn btn-sm" onClick={() => setRev(rev === d.id ? null : d.id)}>Revisar</button>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rev && docs.find((d) => d.id === rev) && <ReviewDoc d={docs.find((d) => d.id === rev)!} cur={curOf(e)} onDone={() => { setRev(null); onChanged(); }} />}
    </div>
  );
}

function ReviewDoc({ d, cur, onDone }: { d: Doc; cur: string; onDone: () => void }) {
  const ex = (d.extracted ?? {}) as Record<string, number | string | boolean>;
  const toTxt = (v: unknown) => (typeof v === "number" ? (v / 100).toFixed(2).replace(".", ",") : "");
  const [f, setF] = useState({ period: String(ex.periodo ?? d.period ?? ""), dev: toTxt(ex.devengado_cents), ded: toTxt(ex.deducciones_cents), liq: toTxt(ex.liquido_cents), note: "" });
  const [err, setErr] = useState<string | null>(null);
  const isSlip = d.kind === "nomina";
  async function send(status: "valido" | "rechazado") {
    setErr(null);
    const body: Record<string, unknown> = { version: d.version, status, note: f.note || null };
    if (isSlip && status === "valido") Object.assign(body, { period: f.period, devengado_cents: parseMoney(f.dev), deducciones_cents: parseMoney(f.ded), liquido_cents: parseMoney(f.liq) });
    try { await api(`/hr/documents/${d.id}/review`, { method: "POST", body: JSON.stringify(body) }); onDone(); }
    catch (x) { setErr(errMsg(x)); }
  }
  const sum = (parseMoney(f.dev) ?? 0) - (parseMoney(f.ded) ?? 0);
  return (
    <div className="notice notice-info" style={{ marginTop: 12 }} aria-label="Revisión del documento">
      <strong>Revisar {d.kind_label.toLowerCase()} · {d.name}</strong>
      {isSlip && <p className="small" style={{ margin: "4px 0" }}>La lectura propone estas cifras (confianza {String(ex.confianza ?? "baja")}{ex.titular_coincide === false ? "; ¡el nombre no coincide con la ficha!" : ""}). Compruébelas con el PDF antes de confirmar.</p>}
      {isSlip && (
        <div className="form-grid">
          <label className="field">Periodo (AAAA-MM)<input value={f.period} onChange={(x) => setF({ ...f, period: x.target.value })} /></label>
          <MoneyInput label={`Total devengado (${cur})`} value={f.dev} onChange={(v) => setF({ ...f, dev: v })} />
          <MoneyInput label="Total a deducir" value={f.ded} onChange={(v) => setF({ ...f, ded: v })} />
          <MoneyInput label="Líquido a percibir" value={f.liq} onChange={(v) => setF({ ...f, liq: v })} />
          <p className="full small" style={{ margin: 0 }}>{parseMoney(f.liq) === sum ? <span className="badge badge-green">Devengado − deducciones = líquido</span> : <span className="badge badge-red">Las cifras no cuadran</span>}</p>
        </div>
      )}
      <label className="field" style={{ marginTop: 8 }}>Nota (obligatoria si no es válido)<input value={f.note} onChange={(x) => setF({ ...f, note: x.target.value })} /></label>
      {err && <div className="error-text small" role="alert">{err}</div>}
      <div className="row" style={{ marginTop: 8 }}>
        <button className="btn btn-sm btn-primary" onClick={() => send("valido")}>Confirmar</button>
        <button className="btn btn-sm" onClick={() => send("rechazado")}>No es válido</button>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ plantilla
function Staff() {
  const [rows, setRows] = useState<Emp[] | null>(null);
  const [q, setQ] = useState("");
  const [sel, setSel] = useState<Emp | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const load = useCallback(() => api<{ items: Emp[] }>(`/hr/employees${q ? `?q=${encodeURIComponent(q)}` : ""}`).then((r) => setRows(r.items)).catch((e) => setErr(errMsg(e))), [q]);
  useEffect(() => { load(); }, [load]);
  const open = (id: string) => api<Emp>(`/hr/employees/${id}`).then(setSel).catch((e) => setErr(errMsg(e)));
  return (
    <div className="stack">
      {err && <div className="notice notice-danger">{err}</div>}
      <form className="row" onSubmit={(e) => { e.preventDefault(); load(); }}>
        <input className="search" aria-label="Buscar en la plantilla" placeholder="Nombre, código o puesto" value={q} onChange={(e) => setQ(e.target.value)} />
      </form>
      <div className="table-wrap">
        <table className="data">
          <thead><tr><th>Persona</th><th>Sede</th><th>Puesto</th><th>Contrato</th><th>Avisos</th></tr></thead>
          <tbody>
            {rows?.length === 0 && <tr><td colSpan={5} className="empty">Sin resultados.</td></tr>}
            {rows?.map((e) => {
              const soon = (d: string | null, days: number) => d && (new Date(d).getTime() - Date.now()) / 864e5 <= days && new Date(d).getTime() >= Date.now() - 864e5;
              return (
                <tr key={e.id} style={{ cursor: "pointer", background: sel?.id === e.id ? "var(--primary-soft)" : undefined }} onClick={() => open(e.id)}>
                  <td><button className="linklike" onClick={() => open(e.id)}>{e.name}</button><div className="small muted mono">{e.code}</div></td>
                  <td>{e.branch}<div className="small muted">{e.organization}</div></td>
                  <td>{e.job_title}<div className="small muted">{e.department ?? ""}</div></td>
                  <td>{CONTRATOS[e.contract_type]}{e.contract_end_date ? ` hasta ${fmtDate(e.contract_end_date)}` : ""}</td>
                  <td>{soon(e.contract_end_date, 30) && <span className="badge badge-red">Vence contrato</span>} {soon(e.trial_end_date, 15) && <span className="badge badge-yellow">Fin de prueba</span>} {e.status !== "activo" && <span className="badge">{ESTADOS[e.status]}</span>}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {sel && <EmployeeDetail key={sel.id + sel.version} e={sel} onChanged={() => { open(sel.id); load(); }} />}
    </div>
  );
}

function Leaves() {
  const [rows, setRows] = useState<Leave[] | null>(null);
  const month = new Date().toLocaleDateString("sv-SE", { timeZone: "Europe/Madrid" }).slice(0, 7);
  const [m, setM] = useState(month);
  const [cal, setCal] = useState<Leave[] | null>(null);
  const load = useCallback(() => { api<Leave[]>("/hr/leaves").then(setRows).catch(() => setRows([])); api<Leave[]>(`/hr/calendar?month=${m}`).then(setCal).catch(() => setCal([])); }, [m]);
  useEffect(() => { load(); }, [load]);
  return (
    <div className="stack">
      <div className="card"><h2>Solicitudes por decidir</h2>{rows && <LeaveTable rows={rows} onChanged={load} queue />}</div>
      <div className="card">
        <div className="row"><h2 style={{ margin: 0 }}>Calendario</h2><input type="month" aria-label="Mes" value={m} onChange={(e) => setM(e.target.value)} style={{ width: "auto" }} /></div>
        <p className="small muted">Ausencias aprobadas y solicitadas del mes. Las bajas aparecen como «ausencia» salvo para RRHH. Festivos de cada sede: pendiente (T-49).</p>
        {cal && <LeaveTable rows={cal} onChanged={load} queue />}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ nóminas
interface PayRow { employee_id: string; code: string; name: string; branch: string; currency: string; estado: string; devengado_cents: number | null; deducciones_cents: number | null; liquido_cents: number | null; devengado_anterior_cents: number | null; diferencia_pct: number | null; revisar: boolean }
function Payroll() {
  const prev = (() => { const d = new Date(); d.setDate(1); d.setMonth(d.getMonth() - 1); return d.toLocaleDateString("sv-SE", { timeZone: "Europe/Madrid" }).slice(0, 7); })();
  const [m, setM] = useState(prev);
  const [r, setR] = useState<{ rows: PayRow[]; previous: string; aviso: string } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { api<{ rows: PayRow[]; previous: string; aviso: string }>(`/hr/payroll?month=${m}`).then((x) => { setR(x); setErr(null); }).catch((e) => setErr(errMsg(e))); }, [m]);
  const ST: Record<string, [string, string]> = { confirmada: ["Confirmada", "badge-green"], por_revisar: ["Por revisar", "badge-yellow"], falta: ["Falta", "badge-red"] };
  return (
    <div className="card stack">
      <div className="row"><h2 style={{ margin: 0 }}>Resumen de nóminas</h2><input type="month" aria-label="Mes de nómina" value={m} onChange={(e) => setM(e.target.value)} style={{ width: "auto" }} /></div>
      {err && <div className="notice notice-danger">{err}</div>}
      {r && <p className="small muted" style={{ margin: 0 }}>{r.aviso} Comparación con {r.previous}; se señala una variación de ±10 % o más.</p>}
      <div className="table-wrap">
        <table className="data">
          <thead><tr><th>Persona</th><th>Estado</th><th style={{ textAlign: "right" }}>Devengado</th><th style={{ textAlign: "right" }}>Deducciones</th><th style={{ textAlign: "right" }}>Líquido</th><th>Mes anterior</th></tr></thead>
          <tbody>
            {r?.rows.map((x) => (
              <tr key={x.employee_id}>
                <td>{x.name}<div className="small muted">{x.code} · {x.branch}</div></td>
                <td><span className={`badge ${ST[x.estado][1]}`}>{ST[x.estado][0]}</span></td>
                <td style={{ textAlign: "right" }}>{fmtMoney(x.devengado_cents, x.currency)}</td>
                <td style={{ textAlign: "right" }}>{fmtMoney(x.deducciones_cents, x.currency)}</td>
                <td style={{ textAlign: "right" }}><strong>{fmtMoney(x.liquido_cents, x.currency)}</strong></td>
                <td>{fmtMoney(x.devengado_anterior_cents, x.currency)}{x.diferencia_pct !== null && <> · <span className={`badge ${x.revisar ? "badge-red" : ""}`}>{x.diferencia_pct > 0 ? "+" : ""}{x.diferencia_pct} %</span></>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ importación
interface ImpRow { line: number; name: string; status: string; missing: string[]; problems: string[]; duplicate_of: string[] }
function Import() {
  const me = useMe();
  const orgs = Object.keys(me.permissions).filter((o) => me.permissions[o].includes("hr.manage"));
  const [org, setOrg] = useState(orgs[0] ?? "");
  const [file, setFile] = useState<File | null>(null);
  const [r, setR] = useState<{ rows: ImpRow[]; created: string[]; columns: string[]; confirmed: boolean } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  async function send(confirm: boolean) {
    setErr(null);
    const fd = new FormData(); fd.append("organization_id", org); fd.append("confirm", String(confirm)); fd.append("file", file!);
    try { setR(await postForm(`/hr/import`, fd)); } catch (x) { setErr(errMsg(x)); }
  }
  const ST: Record<string, string> = { nuevo: "badge-green", duplicado: "badge-yellow", error: "badge-red" };
  return (
    <div className="card stack">
      <p className="small" style={{ margin: 0 }}>Suba la plantilla en CSV (exportada de MN Program o de otra hoja). Primero verá qué filas son nuevas, cuáles parecen duplicadas y cuáles tienen errores; al confirmar solo se crean las nuevas. Nada se sobrescribe ni se borra. Columnas: <span className="mono small">{(r?.columns ?? ["nombre", "apellidos", "sede", "departamento", "categoria", "puesto", "contrato", "jornada", "horas_semana", "fecha_alta", "…"]).join(";")}</span></p>
      <div className="row">
        {orgs.length > 1 && <select aria-label="Entidad" value={org} onChange={(e) => setOrg(e.target.value)} style={{ width: "auto" }}>{me.memberships.filter((m) => orgs.includes(m.organization.id)).map((m) => <option key={m.organization.id} value={m.organization.id}>{m.organization.name}</option>)}</select>}
        <input type="file" aria-label="Plantilla CSV" accept=".csv,.txt" onChange={(e) => { setFile(e.target.files?.[0] ?? null); setR(null); }} style={{ maxWidth: 320 }} />
        <button className="btn btn-sm" disabled={!file} onClick={() => send(false)}>Revisar</button>
        {r && !r.confirmed && r.rows.some((x) => x.status === "nuevo") && <button className="btn btn-sm btn-primary" onClick={() => send(true)}>Crear las {r.rows.filter((x) => x.status === "nuevo").length} nuevas</button>}
      </div>
      {err && <div className="notice notice-danger" role="alert">{err}</div>}
      {r?.confirmed && <div className="notice notice-ok" role="status">Creadas {r.created.length} ficha(s): {r.created.join(", ") || "ninguna"}.</div>}
      {r && (
        <div className="table-wrap">
          <table className="data">
            <thead><tr><th>Fila</th><th>Persona</th><th>Resultado</th><th>Detalle</th></tr></thead>
            <tbody>{r.rows.map((x) => (
              <tr key={x.line}><td>{x.line}</td><td>{x.name || "—"}</td><td><span className={`badge ${ST[x.status]}`}>{x.status}</span></td>
                <td className="small">{[x.missing.length ? `Faltan: ${x.missing.join(", ")}` : "", ...x.problems, x.duplicate_of.length ? `Parece: ${x.duplicate_of.join(", ")}` : ""].filter(Boolean).join(" · ") || "—"}</td></tr>
            ))}</tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default function Page() {
  return <Suspense fallback={<p className="muted">Cargando…</p>}><Rrhh /></Suspense>;
}

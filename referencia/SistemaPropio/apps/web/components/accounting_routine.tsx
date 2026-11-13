"use client";

// Contabilidad F5.4b: rutina de trabajo (pasos que el sistema comprueba) e informes semanales, quincenales y mensuales.
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { fmtDate, fmtDateTime, fmtMoney } from "@/lib/format";

const errMsg = (e: unknown) => (e instanceof ApiError ? e.message : "No se ha podido completar la operación.");
const CAD: Record<string, string> = { diaria: "Hoy", semanal: "Esta semana", quincenal: "Quincena", mensual: "Cierre del mes" };
const STATE: Record<string, [string, string]> = {
  pendiente: ["Pendiente", "badge-yellow"], vencido: ["Vencido", "badge-red"], hecho: ["Hecho", "badge-green"], no_aplica: ["No aplica", ""],
};

interface Item { id: string; step: string; cadence: string; title: string; how: string; period_label: string; due_date: string; status: string; state: string; evidence: string | null; owner: string | null; done_at: string | null; on_time: boolean | null; na_reason: string | null; na_by: string | null; task_id: string | null; can_na: boolean }
interface Compliance { total: number; a_tiempo: number; tarde: number; pendientes: number; vencidos: number; no_aplica: number; cumplimiento_pct: number | null; por_persona: Record<string, { total: number; a_tiempo: number; tarde: number; pendientes: number }> }
interface Routine { today: string; items: Item[]; compliance_month: Compliance; compliance_prev_month: Compliance }
interface Owner { step: string; cadence: string; title: string; owner_id: string | null; owner: string | null; candidates: { id: string; name: string }[]; can_change: boolean }

export function RoutinePanel({ orgId }: { orgId: string }) {
  const [r, setR] = useState<Routine | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [showDone, setShowDone] = useState(false);
  const [owners, setOwners] = useState(false);
  const load = useCallback(() => { api<Routine>(`/accounting/routine?organization_id=${orgId}`).then(setR).catch((e) => setErr(errMsg(e))); }, [orgId]);
  useEffect(() => { load(); }, [load]);
  if (!r) return err ? <div className="notice notice-danger">{err}</div> : <p className="muted">Comprobando la rutina…</p>;
  const open = r.items.filter((x) => x.status === "pendiente");
  const closed = r.items.filter((x) => x.status !== "pendiente");
  const groups = ["diaria", "semanal", "quincenal", "mensual"].map((c) => [c, open.filter((x) => x.cadence === c)] as const).filter(([, l]) => l.length);
  const c = r.compliance_month;
  return (
    <div className="stack">
      <div className="notice notice-info">
        <strong>Cómo funciona</strong>
        Calendario del manual de Dirección: cada día, extractos y conciliación; cada lunes, facturas, pagos, cajas e informe semanal;
        días 1 y 16, informe quincenal; días 1–2 extractos de fin de mes, 3 conciliar, 4 nóminas y facturas, 5 cierre. Un paso se da por
        <span style={{ fontWeight: 700 }}> hecho solo cuando el sistema lo comprueba</span> en los datos; los semanales, quincenales y mensuales están también en la Agenda de su responsable.
      </div>
      <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))" }} aria-label="Cumplimiento del mes">
        <Stat label="Cumplimiento este mes" value={c.cumplimiento_pct == null ? "—" : `${c.cumplimiento_pct} %`} />
        <Stat label="A tiempo" value={String(c.a_tiempo)} />
        <Stat label="Tarde" value={String(c.tarde)} />
        <Stat label="Vencidos sin hacer" value={String(c.vencidos)} red={c.vencidos > 0} />
        <Stat label="Mes anterior" value={r.compliance_prev_month.cumplimiento_pct == null ? "—" : `${r.compliance_prev_month.cumplimiento_pct} %`} />
      </div>
      {!open.length && <div className="notice notice-ok">Todo al día: no hay pasos pendientes.</div>}
      {groups.map(([cad, list]) => (
        <div key={cad} className="card" aria-label={`Rutina ${CAD[cad]}`}>
          <h2 style={{ marginTop: 0 }}>{CAD[cad]}</h2>
          {list.map((x) => <ItemRow key={x.id} x={x} onDone={load} />)}
        </div>
      ))}
      <div className="row">
        <button className="btn btn-sm" onClick={() => setShowDone(!showDone)}>{showDone ? "Ocultar" : "Ver"} lo hecho (últimas 5 semanas)</button>
        <button className="btn btn-sm" onClick={() => setOwners(!owners)}>{owners ? "Cerrar" : "Responsables de cada paso"}</button>
        <button className="btn btn-sm" onClick={load}>Comprobar ahora</button>
      </div>
      {owners && <OwnersCard orgId={orgId} onDone={load} />}
      {showDone && (
        <div className="card">
          <h2 style={{ marginTop: 0 }}>Hecho</h2>
          <div className="table-wrap"><table className="data">
            <thead><tr><th>Paso</th><th>Periodo</th><th>Fecha objetivo</th><th>Responsable</th><th>Resultado</th></tr></thead>
            <tbody>{closed.map((x) => (
              <tr key={x.id}><td>{x.title}</td><td>{x.period_label}</td><td>{fmtDate(x.due_date)}</td><td>{x.owner ?? "—"}</td>
                <td><span className={`badge ${STATE[x.state][1]}`}>{STATE[x.state][0]}</span>
                  {x.status === "hecho" && x.on_time === false && <span className="badge badge-yellow" style={{ marginLeft: 4 }}>tarde</span>}
                  <div className="small muted">{x.status === "no_aplica" ? `${x.na_by}: ${x.na_reason}` : x.evidence}{x.done_at ? ` · ${fmtDateTime(x.done_at)}` : ""}</div></td></tr>
            ))}</tbody>
          </table></div>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, red }: { label: string; value: string; red?: boolean }) {
  return <div className="card" style={{ padding: 12 }}><div className="stat" style={{ fontSize: "1.3rem", color: red ? "var(--danger)" : undefined }}>{value}</div><div className="stat-label">{label}</div></div>;
}

function ItemRow({ x, onDone }: { x: Item; onDone: () => void }) {
  const [na, setNa] = useState(false);
  const [reason, setReason] = useState("");
  const [err, setErr] = useState<string | null>(null);
  async function markNa() {
    setErr(null);
    try { await api(`/accounting/routine/${x.id}/na`, { method: "POST", body: JSON.stringify({ reason }) }); onDone(); }
    catch (e) { setErr(errMsg(e)); }
  }
  return (
    <div className="row" style={{ alignItems: "flex-start", padding: "8px 0", borderTop: "1px solid var(--border)" }} aria-label={`Paso ${x.title}`}>
      <span className={`badge ${STATE[x.state][1]}`} style={{ minWidth: 76, textAlign: "center" }}>{STATE[x.state][0]}</span>
      <div style={{ flex: 1, minWidth: 240 }}>
        <strong>{x.title}</strong> <span className="small muted">· {x.period_label} · para el {fmtDate(x.due_date)} · {x.owner ?? <span className="badge badge-red">sin responsable</span>}{x.task_id ? " · en su Agenda" : ""}</span>
        <div className="small">{x.how}</div>
        {x.evidence && <div className="small muted">Comprobación: {x.evidence}</div>}
        {na && (
          <div className="row" style={{ marginTop: 6 }}>
            <input aria-label={`Motivo no aplica ${x.title}`} placeholder="Por qué no aplica (mínimo 10 caracteres)" value={reason} onChange={(e) => setReason(e.target.value)} style={{ flex: 1, minWidth: 220 }} />
            <button className="btn btn-sm" disabled={reason.trim().length < 10} onClick={markNa}>Confirmar</button>
          </div>
        )}
        {err && <div className="error-text small">{err}</div>}
      </div>
      {x.can_na && !na && <button className="btn btn-sm" onClick={() => setNa(true)}>No aplica…</button>}
    </div>
  );
}

function OwnersCard({ orgId, onDone }: { orgId: string; onDone: () => void }) {
  const [rows, setRows] = useState<Owner[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const load = useCallback(() => { api<Owner[]>(`/accounting/routine/owners?organization_id=${orgId}`).then(setRows).catch((e) => setErr(errMsg(e))); }, [orgId]);
  useEffect(() => { load(); }, [load]);
  async function change(step: string, user_id: string) {
    setErr(null);
    try { await api("/accounting/routine/owners", { method: "PUT", body: JSON.stringify({ organization_id: orgId, step, user_id }) }); load(); onDone(); }
    catch (e) { setErr(errMsg(e)); }
  }
  return (
    <div className="card" aria-label="Responsables de la rutina">
      <h2 style={{ marginTop: 0 }}>Responsables</h2>
      <p className="small muted" style={{ marginTop: 0 }}>Los asigna Dirección. Solo aparecen personas con permiso para ese paso. El cambio se aplica a los pasos que se abran a partir de ahora.</p>
      {err && <div className="notice notice-danger">{err}</div>}
      <div className="table-wrap"><table className="data">
        <thead><tr><th>Paso</th><th>Frecuencia</th><th>Responsable</th></tr></thead>
        <tbody>{rows?.map((o) => (
          <tr key={o.step}><td>{o.title}</td><td>{o.cadence}</td>
            <td>{o.can_change ? (
              <select aria-label={`Responsable de ${o.title}`} value={o.owner_id ?? ""} onChange={(e) => change(o.step, e.target.value)} style={{ width: "auto" }}>
                <option value="" disabled>Sin responsable</option>{o.candidates.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>) : (o.owner ?? "Sin responsable")}</td></tr>
        ))}</tbody>
      </table></div>
    </div>
  );
}

// ------------------------------------------------------------------ informes
interface ReportRow { id: string; kind: string; label: string; period_from: string; period_to: string; version: number; figures_sha256: string; generated_at: string; generated_by: string; reviewed_by: string | null; reviewed_at: string | null; review_note: string | null; resultado_cents: number; cobros_cents: number; fiabilidad: string; cumplimiento_pct: number | null; can_review: boolean }
type Bucket = Record<string, number | null>;
interface ReportFull extends ReportRow { figures: { currency: string; total: Bucket; previous: { label: string; total: Bucket }; deviations: Record<string, number | null>; by_activity: Record<string, Bucket>; by_branch: Record<string, Bucket>; pending: Record<string, number | string[]>; reliability: { level: string }; forecast: { payables: Record<string, number> }; batches: { por_estado: Record<string, { num: number; total_cents: number }> }; routine: Compliance & { vencidos_detalle: { paso: string; periodo: string; responsable: string; motivo: string | null }[] }; close?: { status: string; revision: number } | null; notes: string[] } }
const KIND: Record<string, string> = { semanal: "Semanal", quincenal: "Quincenal", mensual: "Mensual" };
const LINES: [string, string][] = [["ingresos_devengados", "Ingresos devengados"], ["cobros", "Cobros"], ["gastos_proveedores", "Gastos de proveedores (base)"], ["gastos_empleados", "Gastos de empleados (sin IVA)"], ["coste_personal", "Coste de personal"], ["pagos", "Pagos a proveedores"], ["resultado", "Resultado provisional"]];
const PEND: Record<string, string> = { movimientos_sin_conciliar: "Movimientos sin conciliar", facturas_sin_validar: "Facturas sin validar", cobros_sin_confirmar: "Cobros sin confirmar", cierres_caja_sin_validar: "Cierres de caja sin validar", nominas_sin_confirmar: "Nóminas sin confirmar", facturas_vencidas_sin_pagar: "Facturas vencidas sin pagar" };

export function ReportsPanel({ orgId, canGenerate }: { orgId: string; canGenerate: boolean }) {
  const [kind, setKind] = useState("");
  const [rows, setRows] = useState<ReportRow[] | null>(null);
  const [open, setOpen] = useState<ReportFull | null>(null);
  const [gen, setGen] = useState({ kind: "semanal", day: "" });
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const load = useCallback(() => { api<ReportRow[]>(`/accounting/reports?organization_id=${orgId}${kind ? `&kind=${kind}` : ""}`).then(setRows).catch((e) => setErr(errMsg(e))); }, [orgId, kind]);
  useEffect(() => { load(); }, [load]);
  async function show(id: string) { setErr(null); try { setOpen(await api<ReportFull>(`/accounting/reports/${id}`)); } catch (e) { setErr(errMsg(e)); } }
  async function generate() {
    setErr(null);
    try {
      const r = await api<ReportFull>("/accounting/reports", { method: "POST", body: JSON.stringify({ organization_id: orgId, kind: gen.kind, day: gen.day }) });
      setMsg(`Informe ${r.kind} ${r.label} generado (versión ${r.version}).`); setOpen(r); load();
    } catch (e) { setErr(errMsg(e)); }
  }
  return (
    <div className="stack">
      <p className="small muted" style={{ margin: 0 }}>Se generan solos: el <strong>semanal</strong> cada lunes (semana anterior), el <strong>quincenal</strong> los días 1 y 16 y el <strong>mensual</strong> el día 5. Cada informe es una foto con huella que no cambia; quien puede leer Contabilidad recibe un correo sin cifras y Dirección lo marca como revisado.</p>
      {msg && <div className="notice notice-ok" role="status">{msg}</div>}
      {err && <div className="notice notice-danger" role="alert">{err}</div>}
      <div className="row">
        <select aria-label="Tipo de informe" value={kind} onChange={(e) => setKind(e.target.value)} style={{ width: "auto" }}>
          <option value="">Todos</option><option value="semanal">Semanales</option><option value="quincenal">Quincenales</option><option value="mensual">Mensuales</option>
        </select>
        <span className="spacer" />
        {canGenerate && <>
          <select aria-label="Tipo a generar" value={gen.kind} onChange={(e) => setGen({ ...gen, kind: e.target.value })} style={{ width: "auto" }}>
            <option value="semanal">Semanal</option><option value="quincenal">Quincenal</option><option value="mensual">Mensual</option></select>
          <input type="date" aria-label="Un día del periodo" value={gen.day} onChange={(e) => setGen({ ...gen, day: e.target.value })} style={{ width: "auto" }} />
          <button className="btn btn-sm" disabled={!gen.day} onClick={generate}>Generar ahora</button>
        </>}
      </div>
      <div className="table-wrap"><table className="data">
        <thead><tr><th>Tipo</th><th>Periodo</th><th style={{ textAlign: "right" }}>Cobros</th><th style={{ textAlign: "right" }}>Resultado</th><th>Fiabilidad</th><th>Rutina</th><th>Estado</th><th></th></tr></thead>
        <tbody>
          {rows?.length === 0 && <tr><td colSpan={8} className="empty">Aún no hay informes. El primero se genera el próximo lunes, día 1, 5 o 16{canGenerate ? ", o puede generarlo ahora" : ""}.</td></tr>}
          {rows?.map((x) => (
            <tr key={x.id}><td>{KIND[x.kind]}</td><td>{x.label}{x.version > 1 && <span className="small muted"> · v{x.version}</span>}</td>
              <td style={{ textAlign: "right" }}>{fmtMoney(x.cobros_cents)}</td><td style={{ textAlign: "right" }}>{fmtMoney(x.resultado_cents)}</td>
              <td>{x.fiabilidad.replace("_", " ")}</td><td>{x.cumplimiento_pct == null ? "—" : `${x.cumplimiento_pct} %`}</td>
              <td>{x.reviewed_by ? <span className="badge badge-green">Revisado</span> : <span className="badge badge-yellow">Sin revisar</span>}</td>
              <td><button className="btn btn-sm" onClick={() => show(x.id)}>Ver</button></td></tr>
          ))}
        </tbody>
      </table></div>
      {open && <ReportView r={open} onReviewed={(r) => { setOpen(r); setMsg("Informe marcado como revisado."); load(); }} />}
    </div>
  );
}

function ReportView({ r, onReviewed }: { r: ReportFull; onReviewed: (r: ReportFull) => void }) {
  const [note, setNote] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const f = r.figures;
  const cell = (v: number | null | undefined) => (v == null ? <span className="muted">agrupado</span> : fmtMoney(v, f.currency));
  async function review() {
    setErr(null);
    try { onReviewed(await api<ReportFull>(`/accounting/reports/${r.id}/review`, { method: "POST", body: JSON.stringify({ note: note || null }) })); }
    catch (e) { setErr(errMsg(e)); }
  }
  const rt = f.routine;
  return (
    <div className="card stack" aria-label={`Informe ${r.label}`}>
      <div className="row"><h2 style={{ margin: 0 }}>{KIND[r.kind]} · {r.label}</h2><span className="spacer" />
        <a className="btn btn-sm" href={`/api/v1/accounting/reports/${r.id}/file?fmt=pdf`} target="_blank" rel="noreferrer">PDF</a>
        <a className="btn btn-sm" href={`/api/v1/accounting/reports/${r.id}/file?fmt=csv`}>CSV</a></div>
      <div className="small muted">Versión {r.version} · {r.generated_by} · {fmtDateTime(r.generated_at)} · huella <span className="mono">{r.figures_sha256.slice(0, 12)}</span>
        {r.reviewed_by ? ` · revisado por ${r.reviewed_by} el ${fmtDateTime(r.reviewed_at!)}${r.review_note ? `: «${r.review_note}»` : ""}` : ""}</div>
      {f.close !== undefined && <div className="small">Cierre del mes: {f.close ? `revisión ${f.close.revision}, ${f.close.status}` : "sin preparar"} {f.close?.status !== "aprobado" && <span className="badge badge-yellow">cifras provisionales</span>}</div>}
      <div className="table-wrap"><table className="data">
        <thead><tr><th>Concepto</th><th style={{ textAlign: "right" }}>Periodo</th><th style={{ textAlign: "right" }}>{f.previous.label}</th><th></th></tr></thead>
        <tbody>{LINES.map(([k, l]) => { const d = f.deviations[k]; return (
          <tr key={k} style={k === "resultado" ? { fontWeight: 700 } : undefined}><td>{l}</td><td style={{ textAlign: "right" }}>{cell(f.total[k])}</td><td style={{ textAlign: "right" }}>{cell(f.previous.total[k])}</td>
            <td>{d !== undefined && <span className="badge badge-yellow">{d === null ? "nuevo" : `${d > 0 ? "+" : ""}${d} %`}</span>}</td></tr>); })}</tbody>
      </table></div>
      <div className="grid grid-2">
        <div>
          <h3>Por oficina</h3>
          {Object.entries(f.by_branch).map(([b, v]) => <div key={b} className="row small"><span>{b}</span><span className="spacer" />cobros {cell(v.cobros)} · resultado {cell(v.resultado)}</div>)}
          <h3>Pagos previstos</h3>
          <div className="small">Vencido {fmtMoney(f.forecast.payables.vencido)} · 7 días {fmtMoney(f.forecast.payables["7"])} · 8–30 días {fmtMoney(f.forecast.payables["30"])}</div>
          {Object.entries(f.batches.por_estado).map(([s, v]) => <div key={s} className="small">Remesas {s}: {v.num} por {fmtMoney(v.total_cents)}</div>)}
        </div>
        <div>
          <h3>Pendientes · fiabilidad {f.reliability.level.replace("_", " ")}</h3>
          {Object.entries(PEND).map(([k, l]) => <div key={k} className="row small"><span>{l}</span><span className="spacer" /><span className={`badge ${(f.pending[k] as number) ? "badge-red" : "badge-green"}`}>{f.pending[k] as number}</span></div>)}
          <h3>Rutina de trabajo</h3>
          <div className="small">{rt.a_tiempo} a tiempo · {rt.tarde} tarde · {rt.vencidos} vencidos · {rt.no_aplica} no aplican · cumplimiento {rt.cumplimiento_pct == null ? "—" : `${rt.cumplimiento_pct} %`}</div>
          {Object.entries(rt.por_persona).map(([w, v]) => <div key={w} className="small muted">{w}: {v.a_tiempo} a tiempo, {v.tarde} tarde, {v.pendientes} pendientes</div>)}
          {rt.vencidos_detalle.slice(0, 6).map((v, i) => <div key={i} className="small"><span className="badge badge-red">vencido</span> {v.paso} ({v.periodo}) · {v.responsable}</div>)}
        </div>
      </div>
      <ul className="small muted" style={{ margin: 0 }}>{f.notes.map((n) => <li key={n}>{n}</li>)}</ul>
      {r.can_review && (
        <div className="row">
          <input aria-label="Nota de revisión del informe" placeholder="Nota (opcional)" value={note} onChange={(e) => setNote(e.target.value)} style={{ flex: 1, minWidth: 220 }} />
          <button className="btn btn-primary btn-sm" onClick={review}>Marcar como revisado</button>
          {err && <span className="error-text small">{err}</span>}
        </div>
      )}
    </div>
  );
}

"use client";

import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useMe } from "@/components/session";
import { api, ApiError, postForm } from "@/lib/api";
import {
  CATEGORIAS_MOVIMIENTO, ESTADOS_MOVIMIENTO, REGLAS_CONCILIACION, USOS_CUENTA, fmtDate, fmtDateTime, fmtMoney, label,
} from "@/lib/format";

interface ImportInfo {
  id: string; name: string; format: string; period_from: string | null; period_to: string | null;
  opening_cents: number | null; closing_cents: number | null; total_lines: number; new_lines: number;
  duplicate_lines: number; balance_ok: boolean | null; errors: { linea: string; error: string }[]; imported_at: string;
}
interface Account {
  id: string; organization_id: string; name: string; bank_name: string; iban_last4: string; purpose: string;
  activity: string; currency: string; active: boolean; branch: string | null;
  counts: { importados: number; conciliados: number; pendientes: number; errores: number };
  last_import: ImportInfo | null; can_import: boolean; can_reconcile: boolean; can_manage: boolean; demo_statement: boolean;
}
interface MatchRow { id: string; target_type: string; amount_cents: number; rule: string; explanation: string; status: string; label: string; note: string | null; decided_at: string | null }
interface Movement {
  id: string; booking_date: string; value_date: string | null; amount_cents: number; currency: string; description: string;
  reference: string | null; counterparty: string | null; status: string; category: string | null; note: string | null; version: number;
  proposal: { id: string; kind: string; title: string; detail: string | null; priority: string; payload: Record<string, string> | null } | null;
  matches?: MatchRow[]; reconciled_cents?: number; can_reconcile?: boolean;
}
interface ErrorRow { import_id: string; file: string; imported_at: string; line: string; error: string }
interface Candidate { type: "payment" | "refund" | "movement"; id: string; amount_cents: number; label: string; exact: boolean }

type Tab = "pendientes" | "conciliados" | "importados" | "errores";
const TABS: [Tab, string][] = [["pendientes", "Pendientes"], ["conciliados", "Conciliados"], ["importados", "Importados"], ["errores", "Errores"]];
const ST_BADGE: Record<string, string> = { conciliado: "badge-green", traspaso: "badge-green", propuesto: "badge-blue", sin_justificar: "badge-red", parcial: "badge-yellow" };

function errMsg(e: unknown) { return e instanceof ApiError ? e.message : "No se ha podido completar la operación."; }

export function BankPanel() {
  const params = useSearchParams();
  const [accounts, setAccounts] = useState<Account[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [sel, setSel] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("pendientes");
  const [rows, setRows] = useState<Movement[] | ErrorRow[] | null>(null);
  const [mov, setMov] = useState<string | null>(params.get("mov"));
  const [q, setQ] = useState("");
  const [msg, setMsg] = useState<string | null>(null);

  const loadAccounts = useCallback(() => api<Account[]>("/bank/accounts").then((a) => {
    setAccounts(a); setSel((s) => s ?? a[0]?.id ?? null);
  }).catch((e) => setErr(errMsg(e))), []);
  useEffect(() => { loadAccounts(); }, [loadAccounts]);

  const acc = accounts?.find((a) => a.id === sel) ?? null;
  const loadRows = useCallback(() => {
    if (!sel) return;
    setRows(null);
    if (tab === "errores") { api<ErrorRow[]>(`/bank/accounts/${sel}/errors`).then(setRows).catch((e) => setErr(errMsg(e))); return; }
    api<{ items: Movement[] }>(`/bank/accounts/${sel}/movements?tab=${tab}${q ? `&q=${encodeURIComponent(q)}` : ""}`)
      .then((r) => setRows(r.items)).catch((e) => setErr(errMsg(e)));
  }, [sel, tab, q]);
  useEffect(() => { loadRows(); }, [loadRows]);

  function refresh() { loadAccounts(); loadRows(); }

  if (err && !accounts) return <div className="notice notice-danger" role="alert">{err}</div>;
  return (
    <div className="stack">
      <p className="subtitle" style={{ margin: 0 }}>Extractos de cada cuenta (Excel tal como lo descarga del banco, Norma 43, CAMT.053 o CSV), comprobación de saldos y emparejamiento con los cobros. El agente propone y explica; <strong>Contabilidad valida</strong>. Un traspaso entre cuentas propias nunca es un ingreso.</p>
      {msg && <div className="notice notice-ok" role="status">{msg}</div>}
      <BankTools onDone={(t) => { setMsg(t); refresh(); }} empty={accounts?.length === 0} />
      <div className="row" role="tablist" aria-label="Cuentas" style={{ gap: 8 }}>
        {accounts?.map((a) => (
          <button key={a.id} role="tab" aria-selected={a.id === sel} className={`btn ${a.id === sel ? "btn-primary" : ""}`}
            onClick={() => { setSel(a.id); setMov(null); }}>
            {a.name} <span className="small">…{a.iban_last4}</span>
          </button>
        ))}
      </div>
      {acc && (
        <>
          <div className="grid grid-3" style={{ gridTemplateColumns: "repeat(4, minmax(0, 1fr))" }} aria-label="Resumen de la cuenta">
            {([["importados", "Importados"], ["conciliados", "Conciliados"], ["pendientes", "Pendientes"], ["errores", "Errores"]] as const).map(([k, l]) => (
              <button key={k} className="card" style={{ textAlign: "left", cursor: "pointer" }} onClick={() => setTab(k)} aria-label={`${l}: ${acc.counts[k]}`}>
                <div className="stat" style={k === "errores" && acc.counts[k] ? { color: "var(--danger)" } : undefined}>{acc.counts[k]}</div>
                <div className="stat-label">{l}</div>
              </button>
            ))}
          </div>
          <ImportPanel acc={acc} onDone={(t) => { setMsg(t); setTab("pendientes"); setTimeout(refresh, 300); }} />
          <div className="tabs" role="tablist">
            {TABS.map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} onClick={() => { setTab(k); setMov(null); }}>{l}</button>)}
            <span className="spacer" />
            <a className="btn btn-sm" href={`/api/v1/bank/accounts/${acc.id}/export.csv`}>Exportar CSV (gestoría)</a>
            {acc.can_reconcile && <RunButton orgId={acc.organization_id} onDone={(t) => { setMsg(t); refresh(); }} />}
          </div>
          {tab !== "errores" && (
            <form className="row" onSubmit={(e) => { e.preventDefault(); loadRows(); }}>
              <input aria-label="Buscar en concepto" placeholder="Buscar en concepto, referencia u ordenante" value={q} onChange={(e) => setQ(e.target.value)} style={{ maxWidth: 360 }} />
            </form>
          )}
          <div className="inbox-layout bank-layout">
            <div style={{ minWidth: 0 }}>
              {rows === null && <p className="muted">Cargando…</p>}
              {tab === "errores" && rows && <ErrorsTable rows={rows as ErrorRow[]} />}
              {tab !== "errores" && rows && <MovementsTable rows={rows as Movement[]} sel={mov} onSel={setMov} />}
            </div>
            <div style={{ minWidth: 0 }}>
              {mov ? <MovementDetail key={mov} id={mov} onChanged={(t) => { setMsg(t); refresh(); }} />
                : tab !== "errores" && <div className="card"><p className="muted">Elija un movimiento para ver su explicación y conciliarlo.</p></div>}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function ImportPanel({ acc, onDone }: { acc: Account; onDone: (t: string) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [last, setLast] = useState<ImportInfo | null>(acc.last_import);
  const [check, setCheck] = useState<CheckResult | null>(null);
  async function doCheck(f: File) {
    setBusy(true); setErr(null); setCheck(null);
    const fd = new FormData(); fd.append("file", f);
    try { setCheck(await postForm<CheckResult>(`/bank/accounts/${acc.id}/check`, fd)); }
    catch (e) { setErr(errMsg(e)); } finally { setBusy(false); }
  }
  useEffect(() => setLast(acc.last_import), [acc]);
  async function upload(f: File) {
    setBusy(true); setErr(null);
    const fd = new FormData(); fd.append("file", f);
    try {
      const r = await postForm<ImportInfo>(`/bank/accounts/${acc.id}/imports`, fd);
      setLast(r); setFile(null);
      onDone(`Extracto importado: ${r.new_lines} movimiento(s) nuevo(s)${r.duplicate_lines ? `, ${r.duplicate_lines} ya estaban (no se duplican)` : ""}.`);
    } catch (e) { setErr(errMsg(e)); } finally { setBusy(false); }
  }
  async function demo() {
    setErr(null);
    const res = await fetch(`/api/v1/bank/accounts/${acc.id}/demo-statement`, { credentials: "same-origin" });
    if (!res.ok) { setErr("No disponible."); return; }
    const name = (res.headers.get("content-disposition") ?? "").split('filename="')[1]?.replace(/"$/, "") ?? "extracto_FICTICIO.n43";
    upload(new File([await res.blob()], name));
  }
  return (
    <div className="card stack" style={{ gap: 10 }}>
      <div className="row">
        <strong>{acc.bank_name}</strong><span className="badge">{label(USOS_CUENTA, acc.purpose)}</span>
        <span className="small muted">termina en {acc.iban_last4} · {acc.currency}</span>
        {!acc.active && <span className="badge badge-red">Desactivada</span>}
      </div>
      {acc.can_import && acc.active && (
        <form className="row" onSubmit={(e) => { e.preventDefault(); if (file) upload(file); }}>
          <input type="file" aria-label="Extracto bancario" accept=".xlsx,.xls,.n43,.aeb,.txt,.csv,.xml" onChange={(e) => setFile(e.target.files?.[0] ?? null)} style={{ maxWidth: 360 }} />
          <button className="btn btn-primary" disabled={!file || busy}>{busy ? "Leyendo…" : "Importar extracto"}</button>
          <button type="button" className="btn btn-sm" disabled={!file || busy} onClick={() => file && doCheck(file)} title="Lee el archivo y muestra lo que entiende. No guarda nada.">Comprobar sin importar</button>
          {acc.demo_statement && <button type="button" className="btn btn-sm" onClick={demo} disabled={busy} title="Solo en el entorno de desarrollo y pruebas">Importar extracto FICTICIO de prueba</button>}
        </form>
      )}
      {err && <div className="notice notice-danger" role="alert">{err}</div>}
      {check && <CheckCard c={check} onClose={() => setCheck(null)} />}
      {last && (
        <div className={`notice ${last.balance_ok ? "notice-ok" : "notice-warn"}`}>
          <strong>Último extracto: {last.name}</strong>
          {last.period_from && <>Del {fmtDate(last.period_from)} al {fmtDate(last.period_to)} · </>}
          {last.total_lines} línea(s), {last.new_lines} nueva(s){last.duplicate_lines ? `, ${last.duplicate_lines} repetida(s)` : ""} · importado {fmtDateTime(last.imported_at)}.
          <div>
            {last.balance_ok === true && <>Cuadra: saldo inicial {fmtMoney(last.opening_cents)} + movimientos = saldo final {fmtMoney(last.closing_cents)}.</>}
            {last.balance_ok === false && <>No cuadra o hay líneas sin leer: revise la pestaña «Errores».</>}
            {last.balance_ok === null && <>El formato no trae saldos: no se ha podido comprobar el cuadre.</>}
          </div>
        </div>
      )}
    </div>
  );
}

function RunButton({ orgId, onDone }: { orgId: string; onDone: (t: string) => void }) {
  const [busy, setBusy] = useState(false);
  async function run() {
    setBusy(true);
    try {
      const r = await api<{ runs: { summary: Record<string, number> | null; status: string }[] }>(`/bank/reconcile/run?organization_id=${orgId}`, { method: "POST" });
      const s = r.runs[0]?.summary ?? {};
      onDone(`Conciliación revisada: ${s.revisados ?? 0} movimiento(s), ${s.propuestas ?? 0} propuesta(s) nueva(s).`);
    } catch (e) { onDone(errMsg(e)); } finally { setBusy(false); }
  }
  return <button className="btn btn-sm" onClick={run} disabled={busy}>{busy ? "Revisando…" : "Revisar ahora"}</button>;
}

function MovementsTable({ rows, sel, onSel }: { rows: Movement[]; sel: string | null; onSel: (id: string) => void }) {
  return (
    <div className="table-wrap">
      <table className="data">
        <thead><tr><th>Fecha</th><th>Concepto</th><th style={{ textAlign: "right" }}>Importe</th><th>Estado</th></tr></thead>
        <tbody>
          {rows.length === 0 && <tr><td colSpan={4} className="empty">No hay movimientos en esta vista.</td></tr>}
          {rows.map((m) => (
            <tr key={m.id} onClick={() => onSel(m.id)} style={{ cursor: "pointer", background: sel === m.id ? "var(--primary-soft)" : undefined }}>
              <td>{fmtDate(m.booking_date)}</td>
              <td><button className="linklike" onClick={() => onSel(m.id)} style={{ textAlign: "left" }}>{m.description}</button>
                {m.category && <div className="small muted">{label(CATEGORIAS_MOVIMIENTO, m.category)}</div>}</td>
              <td style={{ textAlign: "right", whiteSpace: "nowrap", color: m.amount_cents < 0 ? "var(--danger)" : undefined }}><strong>{fmtMoney(m.amount_cents, m.currency)}</strong></td>
              <td><span className={`badge ${ST_BADGE[m.status] ?? ""}`}>{label(ESTADOS_MOVIMIENTO, m.status)}</span>
                {m.proposal?.priority === "alta" && <div className="small" style={{ color: "var(--danger)" }}>prioridad alta</div>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ErrorsTable({ rows }: { rows: ErrorRow[] }) {
  return (
    <div className="table-wrap">
      <table className="data">
        <thead><tr><th>Extracto</th><th>Línea</th><th>Problema</th></tr></thead>
        <tbody>
          {rows.length === 0 && <tr><td colSpan={3} className="empty">Sin errores: todas las líneas se leyeron y los saldos cuadran.</td></tr>}
          {rows.map((e, i) => (
            <tr key={i}><td>{e.file}<div className="small muted">{fmtDateTime(e.imported_at)}</div></td><td className="mono">{e.line}</td><td>{e.error}</td></tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MovementDetail({ id, onChanged }: { id: string; onChanged: (t: string) => void }) {
  const [m, setM] = useState<Movement | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [mode, setMode] = useState<"" | "manual" | "justify" | "reject">("");
  const load = useCallback(() => api<Movement>(`/bank/movements/${id}`).then(setM).catch((e) => setErr(errMsg(e))), [id]);
  useEffect(() => { load(); }, [load]);
  if (!m) return <div className="card">{err ? <div className="notice notice-danger">{err}</div> : <p className="muted">Cargando…</p>}</div>;
  const done = ["conciliado", "traspaso", "ignorado"].includes(m.status);
  const canMatch = m.proposal?.kind === "conciliacion";
  async function act(path: string, body: object, ok: string) {
    setErr(null);
    try { setM(await api<Movement>(`/bank/movements/${id}/${path}`, { method: "POST", body: JSON.stringify(body) })); setMode(""); setNote(""); onChanged(ok); }
    catch (e) { setErr(errMsg(e)); }
  }
  return (
    <div className="card stack" style={{ gap: 10 }} aria-label="Detalle del movimiento">
      <div className="row"><strong style={{ fontSize: "1.2rem", color: m.amount_cents < 0 ? "var(--danger)" : undefined }}>{fmtMoney(m.amount_cents, m.currency)}</strong>
        <span className={`badge ${ST_BADGE[m.status] ?? ""}`}>{label(ESTADOS_MOVIMIENTO, m.status)}</span></div>
      <div>{m.description}</div>
      <div className="small muted">Fecha {fmtDate(m.booking_date)}{m.value_date ? ` · valor ${fmtDate(m.value_date)}` : ""}{m.reference ? ` · ref. ${m.reference}` : ""}{m.counterparty ? ` · ${m.counterparty}` : ""}</div>
      {m.note && <div className="small"><strong>Nota:</strong> {m.note}</div>}
      {m.proposal && (
        <div className={`notice ${m.proposal.kind === "conciliacion" ? "notice-info" : "notice-warn"}`}>
          <strong>{m.proposal.kind === "conciliacion" ? `Propuesta del agente · ${label(REGLAS_CONCILIACION, m.proposal.payload?.regla ?? "")}` : "Excepción"}</strong>
          <span style={{ whiteSpace: "pre-wrap" }}>{m.proposal.detail}</span>
        </div>
      )}
      {!!m.matches?.length && (
        <div className="stack" style={{ gap: 4 }}>
          <strong className="small">Emparejamientos</strong>
          {m.matches.map((x) => (
            <div key={x.id} className="small"><span className={`badge ${x.status === "validada" ? "badge-green" : x.status === "rechazada" ? "badge-red" : "badge-blue"}`}>{x.status}</span> {x.label} · {fmtMoney(x.amount_cents)}{x.note ? ` · «${x.note}»` : ""}</div>
          ))}
        </div>
      )}
      {err && <div className="notice notice-danger" role="alert">{err}</div>}
      {m.can_reconcile && !done && (
        <>
          <div className="row">
            {canMatch && <button className="btn btn-primary btn-sm" onClick={() => act("validate", { note: note || null }, "Emparejamiento validado: el cobro queda confirmado.")}>Validar propuesta</button>}
            {canMatch && <button className="btn btn-sm" onClick={() => setMode("reject")}>No es correcta</button>}
            <button className="btn btn-sm" onClick={() => setMode("manual")}>Conciliar a mano</button>
            <button className="btn btn-sm" onClick={() => setMode("justify")}>Justificar / ignorar</button>
          </div>
          {mode === "reject" && (
            <form className="stack" style={{ gap: 6 }} onSubmit={(e) => { e.preventDefault(); act("reject", { note }, "Propuesta rechazada."); }}>
              <label className="field">Motivo<input value={note} onChange={(e) => setNote(e.target.value)} minLength={5} required placeholder="Por qué no corresponde" /></label>
              <div className="row"><button className="btn btn-sm btn-danger">Rechazar</button><button type="button" className="btn btn-sm" onClick={() => setMode("")}>Cancelar</button></div>
            </form>
          )}
          {mode === "manual" && <ManualMatch m={m} onSubmit={(targets, n) => act("manual", { targets, note: n, version: m.version }, "Movimiento conciliado a mano.")} onCancel={() => setMode("")} />}
          {mode === "justify" && <Justify m={m} onSubmit={(b) => act("justify", { ...b, version: m.version }, b.ignore ? "Movimiento marcado como ignorado." : "Movimiento justificado.")} onCancel={() => setMode("")} />}
        </>
      )}
    </div>
  );
}

function ManualMatch({ m, onSubmit, onCancel }: { m: Movement; onSubmit: (t: { type: string; id: string }[], note: string) => void; onCancel: () => void }) {
  const [c, setC] = useState<Candidate[] | null>(null);
  const [q, setQ] = useState("");
  const [pick, setPick] = useState<Record<string, Candidate>>({});
  const [note, setNote] = useState("");
  const load = useCallback(() => api<Candidate[]>(`/bank/movements/${m.id}/candidates${q ? `?q=${encodeURIComponent(q)}` : ""}`).then(setC).catch(() => setC([])), [m.id, q]);
  useEffect(() => { load(); }, [load]);
  const sum = useMemo(() => Object.values(pick).reduce((a, x) => a + x.amount_cents, 0), [pick]);
  const left = m.amount_cents - (m.reconciled_cents ?? 0);
  return (
    <form className="stack" style={{ gap: 6 }} onSubmit={(e) => { e.preventDefault(); onSubmit(Object.values(pick).map((x) => ({ type: x.type, id: x.id })), note); }}>
      <div className="row"><input aria-label="Buscar cobro" placeholder="Código de expediente o nombre" value={q} onChange={(e) => setQ(e.target.value)} style={{ maxWidth: 260 }} /><button type="button" className="btn btn-sm" onClick={load}>Buscar</button></div>
      <div className="stack" style={{ gap: 2, maxHeight: 240, overflow: "auto" }}>
        {c?.length === 0 && <p className="small muted">No hay cobros, devoluciones ni movimientos candidatos. Si es un cobro, regístrelo primero en el expediente.</p>}
        {c?.map((x) => (
          <label key={`${x.type}:${x.id}`} className="row small" style={{ gap: 6 }}>
            <input type="checkbox" checked={!!pick[x.id]} onChange={(e) => { const p = { ...pick }; if (e.target.checked) p[x.id] = x; else delete p[x.id]; setPick(p); }} />
            <span>{x.label}</span><strong>{fmtMoney(x.amount_cents)}</strong>{x.exact && <span className="badge badge-green">importe exacto</span>}
          </label>
        ))}
      </div>
      <div className="small">Elegido: <strong>{fmtMoney(sum)}</strong> de {fmtMoney(left)} {sum === left ? <span className="badge badge-green">cuadra</span> : <span className="badge badge-yellow">debe cuadrar exactamente</span>}</div>
      <label className="field">Nota<input value={note} onChange={(e) => setNote(e.target.value)} minLength={5} required placeholder="Cómo lo ha comprobado" /></label>
      <div className="row"><button className="btn btn-sm btn-primary" disabled={sum !== left}>Conciliar</button><button type="button" className="btn btn-sm" onClick={onCancel}>Cancelar</button></div>
    </form>
  );
}

function Justify({ m, onSubmit, onCancel }: { m: Movement; onSubmit: (b: { category: string; note: string; ignore: boolean }) => void; onCancel: () => void }) {
  const [cat, setCat] = useState((m.proposal?.payload?.categoria_sugerida as string) || m.category || "otro");
  const [note, setNote] = useState("");
  const [ignore, setIgnore] = useState(false);
  return (
    <form className="stack" style={{ gap: 6 }} onSubmit={(e) => { e.preventDefault(); onSubmit({ category: cat, note, ignore }); }}>
      <label className="field">Categoría
        <select value={cat} onChange={(e) => setCat(e.target.value)}>
          {Object.entries(CATEGORIAS_MOVIMIENTO).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </label>
      <label className="field">Justificación<input value={note} onChange={(e) => setNote(e.target.value)} minLength={5} required placeholder="Justificante, recibo o motivo" /></label>
      <label className="row small"><input type="checkbox" checked={ignore} onChange={(e) => setIgnore(e.target.checked)} /> Ignorar (no requiere justificante; queda registrado)</label>
      {m.amount_cents > 0 && cat === "cobro" && !ignore && <p className="small error-text">Un ingreso de cliente se concilia con su cobro registrado («Conciliar a mano»).</p>}
      <div className="row"><button className="btn btn-sm btn-primary">Guardar</button><button type="button" className="btn btn-sm" onClick={onCancel}>Cancelar</button></div>
    </form>
  );
}

interface CheckResult { saved: boolean; format: string; columns: { field: string; header: string }[]; account_hint: string | null; account_last4: string; account_matches: boolean | null; lines: number; period_from: string | null; period_to: string | null; credits: { num: number; cents: number }; debits: { num: number; cents: number }; opening_cents: number | null; closing_cents: number | null; balance_ok: boolean | null; errors: { linea: number | string; error: string }[]; errors_total: number; sample: { date: string; amount_cents: number; description: string }[] }
const FORMATOS: Record<string, string> = { xlsx: "Excel (.xlsx)", xls: "Excel (.xls)", csv: "CSV", n43: "Norma 43", camt053: "CAMT.053" };

function CheckCard({ c, onClose }: { c: CheckResult; onClose: () => void }) {
  const ok = c.lines > 0 && c.errors_total === 0 && c.balance_ok !== false;
  return (
    <div className={`notice ${ok ? "notice-ok" : "notice-warn"}`} aria-label="Resultado de la comprobación">
      <div className="row"><span style={{ fontWeight: 700 }}>Comprobación del formato · no se ha guardado nada</span><span className="spacer" /><button className="btn btn-sm" onClick={onClose}>Cerrar</button></div>
      <div className="small">Formato: <b>{FORMATOS[c.format] ?? c.format}</b> · {c.lines} movimiento(s) leídos
        {c.period_from && <> del {fmtDate(c.period_from)} al {fmtDate(c.period_to!)}</>} · {c.credits.num} abonos ({fmtMoney(c.credits.cents)}) y {c.debits.num} cargos ({fmtMoney(c.debits.cents)})</div>
      {c.columns.length > 0 && <div className="small">Columnas reconocidas: {c.columns.map((x) => `${x.field} = «${x.header}»`).join(" · ")}</div>}
      <div className="small">
        {c.balance_ok === true && <>Saldos: inicial {fmtMoney(c.opening_cents)} + movimientos = final {fmtMoney(c.closing_cents)}. <b>Cuadra.</b></>}
        {c.balance_ok === false && <>Saldos: <b>no cuadran</b> (o hay líneas sin leer).</>}
        {c.balance_ok === null && <>El archivo no trae saldos: no se puede comprobar el cuadre.</>}
      </div>
      <div className="small">
        {c.account_matches === true && <>Cuenta del archivo: …{c.account_hint}, coincide con esta cuenta.</>}
        {c.account_matches === false && <>Cuenta del archivo: <b>…{c.account_hint}</b>, distinta de esta (…{c.account_last4}). Para importarlo habría que dar de alta esa cuenta; en esta instalación de pruebas basta con la comprobación.</>}
        {c.account_matches === null && <>El archivo no indica la cuenta.</>}
      </div>
      {c.errors_total > 0 && <div className="small"><b>{c.errors_total} línea(s) sin leer</b> (no se importarían): {c.errors.slice(0, 8).map((e) => `línea ${e.linea}: ${e.error}`).join(" · ")}</div>}
      {c.sample.length > 0 && (
        <div className="table-wrap" style={{ marginTop: 6 }}><table className="data">
          <thead><tr><th>Primeros movimientos</th><th style={{ textAlign: "right" }}>Importe</th><th>Concepto</th></tr></thead>
          <tbody>{c.sample.map((x, i) => <tr key={i}><td>{fmtDate(x.date)}</td><td style={{ textAlign: "right" }}>{fmtMoney(x.amount_cents)}</td><td>{x.description}</td></tr>)}</tbody>
        </table></div>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ alta de cuentas e importación de varios extractos
interface OrgLite { id: string; name: string; branches: { id: string; name: string }[] }
interface AutoResult { results: ({ file: string; ok: true; account: string; account_last4: string; new_lines: number; duplicate_lines: number; balance_ok: boolean | null } | { file: string; ok: false; error: string })[]; imported: number; failed: number }

function BankTools({ onDone, empty }: { onDone: (t: string) => void; empty: boolean }) {
  const me = useMe();
  const [orgs, setOrgs] = useState<OrgLite[]>([]);
  const [open, setOpen] = useState<"" | "cuenta" | "varios">(empty ? "cuenta" : "");
  useEffect(() => { api<OrgLite[]>("/organizations").then(setOrgs).catch(() => setOrgs([])); }, []);
  const withPerm = (perm: string) => orgs.filter((o) => (me.permissions[o.id] ?? []).includes(perm));
  const canManage = withPerm("bank.accounts.manage");
  const canImport = withPerm("bank.import");
  if (!canManage.length && !canImport.length) return empty ? <div className="notice notice-info"><strong>Sin cuentas</strong>Todavía no hay cuentas bancarias dadas de alta.</div> : null;
  return (
    <div className="stack" style={{ gap: 8 }}>
      {empty && <div className="notice notice-info"><strong>Sin cuentas</strong>Dé de alta sus cuentas bancarias (con su IBAN) para importar los extractos.</div>}
      <div className="row">
        {canManage.length > 0 && <button className={`btn btn-sm ${open === "cuenta" ? "btn-primary" : ""}`} onClick={() => setOpen(open === "cuenta" ? "" : "cuenta")}>Nueva cuenta bancaria</button>}
        {canImport.length > 0 && <button className={`btn btn-sm ${open === "varios" ? "btn-primary" : ""}`} onClick={() => setOpen(open === "varios" ? "" : "varios")}>Importar varios extractos a la vez</button>}
      </div>
      {open === "cuenta" && <NewAccount orgs={canManage} onDone={(t) => { onDone(t); }} />}
      {open === "varios" && <MultiImport orgs={canImport} onDone={onDone} />}
    </div>
  );
}

function NewAccount({ orgs, onDone }: { orgs: OrgLite[]; onDone: (t: string) => void }) {
  const [f, setF] = useState({ org: orgs[0]?.id ?? "", name: "", bank_name: "", iban: "", purpose: "otra", activity: "compartida", branch_id: "", currency: "EUR" });
  const [err, setErr] = useState<string | null>(null);
  const org = orgs.find((o) => o.id === f.org);
  async function save(e: React.FormEvent) {
    e.preventDefault(); setErr(null);
    try {
      const a = await api<{ name: string; iban_last4: string }>("/bank/accounts", { method: "POST", body: JSON.stringify({ organization_id: f.org, name: f.name, bank_name: f.bank_name, iban: f.iban, purpose: f.purpose, activity: f.activity, branch_id: f.branch_id || null, currency: f.currency }) });
      onDone(`Cuenta «${a.name}» (…${a.iban_last4}) dada de alta. Ya puede importar sus extractos.`);
      setF({ ...f, name: "", bank_name: "", iban: "" });
    } catch (x) { setErr(errMsg(x)); }
  }
  return (
    <form className="card form-grid" onSubmit={save} aria-label="Nueva cuenta bancaria">
      {orgs.length > 1 && <label className="field">Entidad<select value={f.org} onChange={(e) => setF({ ...f, org: e.target.value })}>{orgs.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}</select></label>}
      <label className="field">Nombre de la cuenta *<input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="p. ej. CaixaBank cobros Barcelona" required minLength={3} /></label>
      <label className="field">Banco *<input value={f.bank_name} onChange={(e) => setF({ ...f, bank_name: e.target.value })} placeholder="CaixaBank, BBVA, Santander…" required minLength={2} /></label>
      <label className="field">IBAN completo *<input value={f.iban} onChange={(e) => setF({ ...f, iban: e.target.value })} placeholder="ES00 0000 0000 0000 0000 0000" required /><span className="small muted">Se guarda cifrado; en pantalla solo se ven los 4 últimos dígitos.</span></label>
      <label className="field">Uso<select value={f.purpose} onChange={(e) => setF({ ...f, purpose: e.target.value })}>{Object.entries(USOS_CUENTA).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
      <label className="field">Actividad<select value={f.activity} onChange={(e) => setF({ ...f, activity: e.target.value })}><option value="laboral">Laboral</option><option value="extranjeria">Extranjería</option><option value="compartida">Compartida</option></select></label>
      <label className="field">Sede<select value={f.branch_id} onChange={(e) => setF({ ...f, branch_id: e.target.value })}><option value="">General</option>{org?.branches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}</select></label>
      <label className="field">Moneda<select value={f.currency} onChange={(e) => setF({ ...f, currency: e.target.value })}><option>EUR</option><option>USD</option><option>COP</option></select></label>
      {err && <div className="full notice notice-danger" role="alert">{err}</div>}
      <div className="full"><button className="btn btn-primary">Dar de alta la cuenta</button></div>
    </form>
  );
}

function MultiImport({ orgs, onDone }: { orgs: OrgLite[]; onDone: (t: string) => void }) {
  const [org, setOrg] = useState(orgs[0]?.id ?? "");
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<AutoResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  async function go() {
    setBusy(true); setErr(null); setRes(null);
    const fd = new FormData(); fd.append("organization_id", org); files.forEach((x) => fd.append("files", x));
    try { const r = await postForm<AutoResult>("/bank/imports/auto", fd); setRes(r); onDone(`${r.imported} extracto(s) importado(s)${r.failed ? `, ${r.failed} con incidencias (ver detalle)` : ""}.`); }
    catch (e) { setErr(errMsg(e)); } finally { setBusy(false); }
  }
  return (
    <div className="card stack" style={{ gap: 8 }} aria-label="Importar varios extractos">
      <p className="small muted" style={{ margin: 0 }}>Seleccione todos los extractos (Excel, Norma 43, CAMT.053 o CSV) de todas las cuentas. Cada uno se importa en la cuenta cuyo IBAN termina igual que el del extracto; si el archivo no indica la cuenta, se le avisa para importarlo desde esa cuenta. Nada se duplica si sube dos veces el mismo extracto.</p>
      <div className="row">
        {orgs.length > 1 && <select aria-label="Entidad de los extractos" value={org} onChange={(e) => setOrg(e.target.value)} style={{ width: "auto" }}>{orgs.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}</select>}
        <input type="file" multiple aria-label="Extractos bancarios" accept=".xlsx,.xls,.n43,.aeb,.txt,.csv,.xml" onChange={(e) => setFiles(Array.from(e.target.files ?? []))} style={{ maxWidth: 420 }} />
        <button className="btn btn-primary" disabled={!files.length || busy} onClick={go}>{busy ? `Importando ${files.length}…` : `Importar ${files.length || ""} extracto(s)`}</button>
      </div>
      {err && <div className="notice notice-danger" role="alert">{err}</div>}
      {res && (
        <div className="table-wrap"><table className="data" aria-label="Resultado de la importación">
          <thead><tr><th>Archivo</th><th>Cuenta</th><th>Resultado</th></tr></thead>
          <tbody>{res.results.map((r, i) => (
            <tr key={i}><td>{r.file}</td><td>{r.ok ? `${r.account} (…${r.account_last4})` : "—"}</td>
              <td>{r.ok ? <><span className="badge badge-green">Importado</span> {r.new_lines} nuevo(s){r.duplicate_lines ? `, ${r.duplicate_lines} ya estaban` : ""}{r.balance_ok === false ? <> · <span className="badge badge-red">saldos no cuadran</span></> : ""}</>
                : <><span className="badge badge-red">No importado</span> <span className="small">{r.error}</span></>}</td></tr>
          ))}</tbody>
        </table></div>
      )}
    </div>
  );
}

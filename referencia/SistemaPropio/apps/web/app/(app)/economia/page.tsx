"use client";

import { useCallback, useEffect, useState } from "react";
import { CaseEconomy, MoneyInput, PaymentForm, RefundDetail, RefundRequestForm, StatusBadge, type Refund } from "@/components/economy";
import { useMe } from "@/components/session";
import { api, ApiError, hasPerm } from "@/lib/api";
import { ESTADOS_DEVOLUCION, METODOS_COBRO, TIPOS_CAJA, fmtDateTime, fmtMoney, label, parseMoney } from "@/lib/format";

type Tab = "expediente" | "cobros" | "devoluciones" | "caja" | "resumen";

export default function Economia() {
  const me = useMe();
  const tabs: [Tab, string, boolean][] = [
    ["expediente", "Buscar expediente", hasPerm(me, "payment.register") || hasPerm(me, "refund.request") || hasPerm(me, "economy.read.all")],
    ["cobros", "Cobros por confirmar", hasPerm(me, "payment.confirm")],
    ["devoluciones", "Devoluciones", hasPerm(me, "refund.request") || hasPerm(me, "refund.review") || hasPerm(me, "refund.decide") || hasPerm(me, "refund.legal_opinion")],
    ["caja", "Caja", hasPerm(me, "cash.operate") || hasPerm(me, "cash.read.all")],
    ["resumen", "Resumen", hasPerm(me, "economy.report")],
  ];
  const visible = tabs.filter((t) => t[2]);
  const [tab, setTab] = useState<Tab>(visible[0]?.[0] ?? "expediente");
  if (!visible.length) return <div className="notice notice-warn"><strong>Sin acceso</strong>Su rol no tiene funciones económicas.</div>;
  return (
    <div className="stack">
      <div className="topline">
        <div>
          <h1>Economía</h1>
          <p className="subtitle">Control interno de cobros, devoluciones y cajas. <strong>No emite facturas</strong>: la factura se hace en el programa homologado (decisión D-25).</p>
        </div>
      </div>
      <div className="tabs" role="tablist">
        {visible.map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? "active" : undefined} onClick={() => setTab(k)}>{l}</button>)}
      </div>
      {tab === "expediente" && <Lookup />}
      {tab === "cobros" && <PendingPayments />}
      {tab === "devoluciones" && <Refunds />}
      {tab === "caja" && <Cash />}
      {tab === "resumen" && <Summary />}
    </div>
  );
}

interface Match { case_id: string; code: string; materia: string; status: string; organization: string; contact_name: string | null; can_pay: boolean; can_refund: boolean; can_read: boolean; branches: { id: string; name: string }[] }

function Lookup() {
  const [code, setCode] = useState("");
  const [rows, setRows] = useState<Match[] | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [action, setAction] = useState<Record<string, "pay" | "refund" | undefined>>({});
  async function search(e: React.FormEvent) {
    e.preventDefault(); setMsg(null);
    setRows(await api<Match[]>(`/economy/lookup?code=${encodeURIComponent(code)}`).catch(() => []));
  }
  return (
    <div className="card">
      <form className="row" onSubmit={search}>
        <input aria-label="Código de expediente" placeholder="Código del expediente, p. ej. LAB-2026-0001" value={code} onChange={(e) => setCode(e.target.value)} style={{ maxWidth: 320 }} required />
        <button className="btn">Buscar</button>
      </form>
      {msg && <div className="notice notice-ok" style={{ marginTop: 10 }}>{msg}</div>}
      {rows?.length === 0 && <p className="empty">No hay ningún expediente con ese código a su alcance.</p>}
      {rows?.map((m) => (
        <div key={m.case_id} className="stack" style={{ marginTop: 14 }}>
          <div className="row"><span className="badge mono">{m.code}</span><span>{m.organization}</span>{m.contact_name && <strong>{m.contact_name}</strong>}<span className="badge">{m.materia}</span></div>
          {m.can_read ? <CaseEconomy caseId={m.case_id} /> : (
            <div className="card" style={{ background: "var(--surface-2)" }}>
              <div className="row">
                {m.can_pay && <button className="btn btn-sm" onClick={() => setAction({ ...action, [m.case_id]: "pay" })}>Registrar cobro</button>}
                {m.can_refund && <button className="btn btn-sm" onClick={() => setAction({ ...action, [m.case_id]: "refund" })}>Solicitar devolución</button>}
              </div>
              {action[m.case_id] === "pay" && <PaymentForm caseId={m.case_id} branches={m.branches} onDone={(t) => { setMsg(t); setAction({}); }} />}
              {action[m.case_id] === "refund" && <RefundRequestForm caseId={m.case_id} onDone={(t) => { setMsg(t); setAction({}); }} />}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

interface PaymentRow { id: string; amount_cents: number; currency: string; method: string; received_at: string; reference: string | null; branch: string | null; registered_by: string; case_code: string; contact_name: string; status: string }

function PendingPayments() {
  const [rows, setRows] = useState<PaymentRow[] | null>(null);
  const [inv, setInv] = useState<Record<string, string>>({});
  const [annul, setAnnul] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => api<PaymentRow[]>("/economy/payments?status=registrado").then(setRows).catch(() => setRows([])), []);
  useEffect(() => { load(); }, [load]);
  async function confirm(id: string) {
    setError(null);
    try { await api(`/economy/payments/${id}/confirm`, { method: "POST", body: JSON.stringify({ invoice_ref: inv[id] || null }) }); load(); }
    catch (e) { setError(e instanceof ApiError ? e.message : "Error"); }
  }
  async function doAnnul(e: React.FormEvent) {
    e.preventDefault(); setError(null);
    try { await api(`/economy/payments/${annul}/annul`, { method: "POST", body: JSON.stringify({ reason }) }); setAnnul(null); setReason(""); load(); }
    catch (err) { setError(err instanceof ApiError ? err.message : "Error"); }
  }
  return (
    <div className="card">
      <p className="small muted">Compruebe cada cobro en el banco o en la caja y confírmelo. Si ya ha emitido la factura en el programa homologado, anote su número.</p>
      {error && <div className="notice notice-danger">{error}</div>}
      <div className="table-wrap">
        <table className="data">
          <thead><tr><th>Fecha</th><th>Expediente</th><th>Forma</th><th>Importe</th><th>Nº factura</th><th></th></tr></thead>
          <tbody>
            {rows?.length === 0 && <tr><td colSpan={6} className="empty">No hay cobros pendientes de confirmar.</td></tr>}
            {rows?.map((x) => (
              <tr key={x.id}>
                <td>{fmtDateTime(x.received_at)}<div className="small muted">{x.registered_by}</div></td>
                <td><span className="mono">{x.case_code}</span><div className="small">{x.contact_name}</div></td>
                <td>{label(METODOS_COBRO, x.method)}{x.branch ? ` · ${x.branch}` : ""}<div className="small muted">{x.reference}</div></td>
                <td><strong>{fmtMoney(x.amount_cents, x.currency)}</strong></td>
                <td><input aria-label={`Factura de ${x.case_code}`} style={{ width: 140 }} placeholder="opcional" value={inv[x.id] ?? ""} onChange={(e) => setInv({ ...inv, [x.id]: e.target.value })} /></td>
                <td className="row"><button className="btn btn-sm btn-primary" onClick={() => confirm(x.id)}>Confirmar</button>
                  <button className="btn btn-sm" onClick={() => setAnnul(x.id)}>Anular</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {annul && (
        <form className="row" style={{ marginTop: 10 }} onSubmit={doAnnul}>
          <input aria-label="Motivo de anulación" placeholder="Motivo de la anulación" value={reason} onChange={(e) => setReason(e.target.value)} minLength={5} required style={{ flex: 1 }} />
          <button className="btn btn-sm btn-warn">Anular cobro</button><button type="button" className="btn btn-sm" onClick={() => setAnnul(null)}>Cancelar</button>
        </form>
      )}
    </div>
  );
}

function Refunds() {
  const [status, setStatus] = useState("");
  const [rows, setRows] = useState<Refund[] | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const load = useCallback(() => api<Refund[]>(`/economy/refunds${status ? `?status=${status}` : ""}`).then(setRows).catch(() => setRows([])), [status]);
  useEffect(() => { load(); }, [load]);
  return (
    <div className="card">
      <div className="row">
        <select aria-label="Estado" style={{ width: 220 }} value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">Todas</option>
          {Object.entries(ESTADOS_DEVOLUCION).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <span className="small muted">ATC registra, investiga y escala · el letrado informa · Contabilidad aprueba o rechaza y paga.</span>
      </div>
      <div className="table-wrap" style={{ marginTop: 10 }}>
        <table className="data">
          <thead><tr><th>Fecha</th><th>Expediente</th><th>Motivo</th><th>Importe</th><th>Estado</th></tr></thead>
          <tbody>
            {rows?.length === 0 && <tr><td colSpan={5} className="empty">No hay devoluciones.</td></tr>}
            {rows?.map((r) => (
              <tr key={r.id} className="clickable" onClick={() => setOpen(open === r.id ? null : r.id)}>
                <td>{fmtDateTime(r.created_at)}<div className="small muted">{r.requested_by}</div></td>
                <td><span className="mono">{r.case_code}</span><div className="small">{r.contact_name}</div></td>
                <td className="small">{r.reason.slice(0, 90)}</td>
                <td>{fmtMoney(r.amount_cents, r.currency)}</td>
                <td><StatusBadge map={ESTADOS_DEVOLUCION} s={r.status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {open && <RefundDetail key={open} id={open} onChange={load} />}
    </div>
  );
}

interface CashBox {
  branch_id: string; branch: string; organization: string; currency: string; balance_cents: number; can_operate: boolean;
  last_closing: { at: string; expected_cents: number; counted_cents: number; difference_cents: number; by: string; notes: string | null } | null;
  movements: { id: string; kind: string; amount_cents: number; concept: string; at: string; by: string }[];
}

function Cash() {
  const [boxes, setBoxes] = useState<CashBox[] | null>(null);
  const load = useCallback(() => api<CashBox[]>("/economy/cash").then(setBoxes).catch(() => setBoxes([])), []);
  useEffect(() => { load(); }, [load]);
  return (
    <div className="stack">
      {boxes?.map((b) => <CashCard key={b.branch_id} b={b} onChange={load} />)}
      {boxes?.length === 0 && <p className="empty">No tiene cajas a su cargo.</p>}
    </div>
  );
}

function CashCard({ b, onChange }: { b: CashBox; onChange: () => void }) {
  const [mode, setMode] = useState<"" | "move" | "close">("");
  const [kind, setKind] = useState("gasto");
  const [amount, setAmount] = useState("");
  const [concept, setConcept] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  async function submit(e: React.FormEvent) {
    e.preventDefault(); setError(null); setMsg(null);
    const cents = parseMoney(amount);
    if (cents === null) return;
    try {
      if (mode === "move") await api(`/economy/cash/${b.branch_id}/movements`, { method: "POST", body: JSON.stringify({ kind, amount_cents: cents, concept }) });
      else {
        const r = await api<{ difference_cents: number }>(`/economy/cash/${b.branch_id}/closings`, { method: "POST", body: JSON.stringify({ counted_cents: cents, notes: notes || null }) });
        setMsg(r.difference_cents === 0 ? "Arqueo cuadrado." : `Arqueo registrado con una diferencia de ${fmtMoney(r.difference_cents, b.currency)}.`);
      }
      setMode(""); setAmount(""); setConcept(""); setNotes(""); onChange();
    } catch (err) { setError(err instanceof ApiError ? err.message : "Error"); }
  }
  return (
    <div className="card" aria-label={`Caja ${b.branch}`}>
      <div className="row">
        <h2 style={{ margin: 0 }}>Caja {b.branch}</h2><span className="small muted">{b.organization}</span><span className="spacer" />
        <strong style={{ fontSize: "1.3rem" }}>{fmtMoney(b.balance_cents, b.currency)}</strong>
      </div>
      {b.last_closing && <p className="small muted">Último arqueo {fmtDateTime(b.last_closing.at)} por {b.last_closing.by}: contado {fmtMoney(b.last_closing.counted_cents, b.currency)}
        {b.last_closing.difference_cents !== 0 && <> · diferencia <strong>{fmtMoney(b.last_closing.difference_cents, b.currency)}</strong> ({b.last_closing.notes})</>}</p>}
      {msg && <div className="notice notice-ok">{msg}</div>}
      {b.can_operate && (
        <div className="row" style={{ margin: "8px 0" }}>
          <button className="btn btn-sm" onClick={() => setMode(mode === "move" ? "" : "move")}>Movimiento</button>
          <button className="btn btn-sm btn-primary" onClick={() => setMode(mode === "close" ? "" : "close")}>Arqueo</button>
        </div>
      )}
      {mode && (
        <form className="form-grid" onSubmit={submit}>
          {error && <div className="notice notice-danger full">{error}</div>}
          {mode === "move" ? <>
            <label className="field">Tipo
              <select value={kind} onChange={(e) => setKind(e.target.value)}>
                <option value="gasto">Gasto pagado con la caja</option><option value="ingreso_banco">Ingreso en el banco</option><option value="aportacion">Aportación a la caja</option>
              </select>
            </label>
            <MoneyInput label="Importe" value={amount} onChange={setAmount} />
            <label className="field full">Concepto<input value={concept} onChange={(e) => setConcept(e.target.value)} minLength={3} required /></label>
          </> : <>
            <p className="full small" style={{ margin: 0 }}>Según los registros debería haber <strong>{fmtMoney(b.balance_cents, b.currency)}</strong>. Cuente el efectivo e indique el total.</p>
            <MoneyInput label="Efectivo contado" value={amount} onChange={setAmount} />
            <label className="field">Observaciones <span className="hint">obligatorias si no cuadra</span><input value={notes} onChange={(e) => setNotes(e.target.value)} /></label>
          </>}
          <div className="full row"><button className="btn btn-primary btn-sm">Guardar</button><button type="button" className="btn btn-sm" onClick={() => setMode("")}>Cancelar</button></div>
        </form>
      )}
      <div className="table-wrap">
        <table className="data">
          <thead><tr><th>Fecha</th><th>Tipo</th><th>Concepto</th><th style={{ textAlign: "right" }}>Importe</th></tr></thead>
          <tbody>
            {b.movements.map((m) => (
              <tr key={m.id}><td>{fmtDateTime(m.at)}<div className="small muted">{m.by}</div></td><td>{label(TIPOS_CAJA, m.kind)}</td>
                <td className="small">{m.concept.replace(/ \[gasto [0-9a-f-]+\]$/, "")}</td>
                <td style={{ textAlign: "right", color: m.amount_cents < 0 ? "var(--danger)" : undefined }}>{fmtMoney(m.amount_cents, b.currency)}</td></tr>
            ))}
            {b.movements.length === 0 && <tr><td colSpan={4} className="empty">Sin movimientos.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

interface SummaryRow { organization: string; currency: string; por_sede: Record<string, { cobrado: number; confirmado: number; pendiente_confirmar: number; cobros: number; por_metodo: Record<string, number> }>; devuelto: number; devoluciones_abiertas: number; pendiente_de_cobro_total: number }

function Summary() {
  const today = new Date();
  const first = new Date(today.getFullYear(), today.getMonth(), 1);
  const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const [from, setFrom] = useState(iso(first));
  const [to, setTo] = useState(iso(today));
  const [rows, setRows] = useState<SummaryRow[] | null>(null);
  useEffect(() => { api<SummaryRow[]>(`/economy/summary?from=${from}&to=${to}`).then(setRows).catch(() => setRows([])); }, [from, to]);
  return (
    <div className="stack">
      <div className="card row">
        <label className="field">Desde<input type="date" value={from} onChange={(e) => setFrom(e.target.value)} /></label>
        <label className="field">Hasta<input type="date" value={to} onChange={(e) => setTo(e.target.value)} /></label>
      </div>
      {rows?.map((o) => (
        <div key={o.organization} className="card">
          <h2 style={{ marginTop: 0 }}>{o.organization}</h2>
          <div className="grid grid-3">
            <div className="stat"><div className="stat-label">Pendiente de cobro (total)</div><strong>{fmtMoney(o.pendiente_de_cobro_total, o.currency)}</strong></div>
            <div className="stat"><div className="stat-label">Devuelto en el periodo</div><strong>{fmtMoney(o.devuelto, o.currency)}</strong></div>
            <div className="stat"><div className="stat-label">Devoluciones abiertas</div><strong>{o.devoluciones_abiertas}</strong></div>
          </div>
          <table className="data" style={{ marginTop: 12 }}>
            <thead><tr><th>Sede</th><th>Cobros</th><th>Cobrado</th><th>Confirmado</th><th>Por confirmar</th><th>Por forma de pago</th></tr></thead>
            <tbody>
              {Object.entries(o.por_sede).map(([s, v]) => (
                <tr key={s}><td>{s}</td><td>{v.cobros}</td><td>{fmtMoney(v.cobrado, o.currency)}</td><td>{fmtMoney(v.confirmado, o.currency)}</td><td>{fmtMoney(v.pendiente_confirmar, o.currency)}</td>
                  <td className="small">{Object.entries(v.por_metodo).map(([m, c]) => `${label(METODOS_COBRO, m)}: ${fmtMoney(c, o.currency)}`).join(" · ")}</td></tr>
              ))}
              {Object.keys(o.por_sede).length === 0 && <tr><td colSpan={6} className="empty">Sin cobros en el periodo.</td></tr>}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
}

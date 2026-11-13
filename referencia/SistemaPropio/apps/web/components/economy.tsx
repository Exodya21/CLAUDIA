"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError, fieldErrors } from "@/lib/api";
import {
  ACCION_DEVOLUCION, ESTADOS_COBRO, ESTADOS_DEVOLUCION, METODOS_COBRO, TIPOS_CARGO, fmtDate, fmtDateTime, fmtMoney, label, parseMoney,
} from "@/lib/format";

export interface Totals { cargado: number; cobrado: number; cobrado_confirmado: number; devuelto: number; pendiente: number; devolvible: number }
export interface Refund {
  id: string; amount_cents: number; currency: string; reason: string; status: string; requested_by: string; created_at: string;
  legal_opinion: string | null; legal_opinion_by: string | null; decided_by: string | null; decision_reason: string | null;
  pay_method: string | null; pay_reference: string | null; version: number; case_code?: string; contact_name?: string;
  events?: { from: string | null; to: string; note: string | null; actor: string; at: string }[];
  allowed?: string[]; totals?: Totals | null; organization_id: string;
}
interface CaseEco {
  case_id: string; code: string; currency: string; totals: Totals; aviso: string;
  charges: { id: string; kind: string; concept: string; amount_cents: number; due_date: string | null; status: string; created_by: string; cancel_reason: string | null }[];
  payments: { id: string; amount_cents: number; method: string; received_at: string; reference: string | null; status: string; invoice_ref: string | null; branch: string | null; registered_by: string }[];
  refunds: Refund[];
  can: { charge: boolean; cancel_charge: boolean; pay: boolean; confirm: boolean; refund: boolean };
  branches: { id: string; name: string }[];
}

export function StatusBadge({ map, s }: { map: Record<string, string>; s: string }) {
  const green = ["confirmado", "pagada", "conciliado", "aprobado", "aprobada", "vigente"];
  const red = ["anulado", "rechazada", "devuelto"];
  const yellow = ["registrado", "registrada", "en_revision", "escalada_legal", "enviado", "borrador"];
  const cls = green.includes(s) ? "badge-green" : red.includes(s) ? "badge-red" : yellow.includes(s) ? "badge-yellow" : "";
  return <span className={`badge ${cls}`}>{label(map, s)}</span>;
}

export function MoneyInput({ value, onChange, label: lbl, error, optional }: { value: string; onChange: (v: string) => void; label: string; error?: string; optional?: boolean }) {
  const bad = value !== "" && parseMoney(value) === null;
  return (
    <label className="field">{lbl}
      <input inputMode="decimal" placeholder="0,00" value={value} onChange={(e) => onChange(e.target.value)} className={bad || error ? "invalid" : undefined} required={!optional} />
      {(bad || error) && <span className="error-text">{error ?? "Importe no válido (ej. 45,50)"}</span>}
    </label>
  );
}

/** Registrar un cobro: lo usan la ficha del expediente y la pantalla Economía (Recepción). */
export function PaymentForm({ caseId, branches, onDone }: { caseId: string; branches: { id: string; name: string }[]; onDone: (msg: string) => void }) {
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState("efectivo");
  const [branch, setBranch] = useState(branches[0]?.id ?? "");
  const [reference, setReference] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [fe, setFe] = useState<Record<string, string>>({});
  async function submit(e: React.FormEvent) {
    e.preventDefault(); setError(null); setFe({});
    const cents = parseMoney(amount);
    if (!cents) return;
    try {
      await api(`/economy/cases/${caseId}/payments`, { method: "POST", body: JSON.stringify({
        amount_cents: cents, method, branch_id: method === "efectivo" || method === "tarjeta" ? branch || null : null, reference: reference || null }) });
      setAmount(""); setReference("");
      onDone(`Cobro de ${fmtMoney(cents)} registrado. Contabilidad lo confirmará.`);
    } catch (err) { setFe(fieldErrors(err)); setError(err instanceof ApiError ? err.message : "No se pudo registrar."); }
  }
  return (
    <form className="form-grid" onSubmit={submit} aria-label="Registrar cobro">
      {error && <div className="notice notice-danger full">{error}</div>}
      <MoneyInput label="Importe recibido" value={amount} onChange={setAmount} />
      <label className="field">Forma de pago
        <select value={method} onChange={(e) => setMethod(e.target.value)}>
          {["efectivo", "tarjeta", "transferencia", "bizum"].map((m) => <option key={m} value={m}>{label(METODOS_COBRO, m)}</option>)}
        </select>
      </label>
      {(method === "efectivo" || method === "tarjeta") && (
        <label className="field">Sede {method === "efectivo" && <span className="hint">entra en esta caja</span>}
          <select value={branch} onChange={(e) => setBranch(e.target.value)} className={fe.branch_id ? "invalid" : undefined}>
            {branches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select>
        </label>
      )}
      {method !== "efectivo" && (
        <label className="field">Referencia {method === "tarjeta" ? <span className="hint">opcional (nº de operación)</span> : null}
          <input value={reference} onChange={(e) => setReference(e.target.value)} className={fe.reference ? "invalid" : undefined} required={method !== "tarjeta"} />
        </label>
      )}
      <div className="full"><button className="btn btn-primary">Registrar cobro</button></div>
    </form>
  );
}

export function RefundRequestForm({ caseId, onDone }: { caseId: string; onDone: (msg: string) => void }) {
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  async function submit(e: React.FormEvent) {
    e.preventDefault(); setError(null);
    const cents = parseMoney(amount);
    if (!cents) return;
    try {
      await api(`/economy/cases/${caseId}/refunds`, { method: "POST", body: JSON.stringify({ amount_cents: cents, reason }) });
      setAmount(""); setReason("");
      onDone("Solicitud de devolución registrada. La decide Contabilidad.");
    } catch (err) { setError(err instanceof ApiError ? err.message : "No se pudo registrar."); }
  }
  return (
    <form className="form-grid" onSubmit={submit} aria-label="Solicitar devolución">
      {error && <div className="notice notice-danger full">{error}</div>}
      <MoneyInput label="Importe que solicita el cliente" value={amount} onChange={setAmount} />
      <label className="field full">Qué pide el cliente y por qué (mínimo 10 caracteres)
        <textarea rows={2} value={reason} onChange={(e) => setReason(e.target.value)} minLength={10} required />
      </label>
      <p className="full small muted" style={{ margin: 0 }}>Registrar no compromete nada: la viabilidad no la decide quien registra, y solo Contabilidad aprueba devoluciones.</p>
      <div className="full"><button className="btn btn-primary">Registrar solicitud</button></div>
    </form>
  );
}

/** Ficha de una devolución con las acciones que el servidor permite a este perfil. */
export function RefundDetail({ id, onChange }: { id: string; onChange?: () => void }) {
  const [r, setR] = useState<Refund | null>(null);
  const [to, setTo] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [payMethod, setPayMethod] = useState("transferencia");
  const [payRef, setPayRef] = useState("");
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => api<Refund>(`/economy/refunds/${id}`).then(setR).catch((e) => setError(e.message)), [id]);
  useEffect(() => { load(); }, [load]);
  if (!r) return error ? <div className="notice notice-danger">{error}</div> : <p className="muted">Cargando…</p>;
  const legalStep = r.status === "escalada_legal";
  async function go(e: React.FormEvent) {
    e.preventDefault(); setError(null);
    try {
      const body: Record<string, unknown> = { to, note: note || null, version: r!.version };
      if (to === "pagada") Object.assign(body, { pay_method: payMethod, pay_reference: payRef || null });
      setR(await api<Refund>(`/economy/refunds/${id}/transition`, { method: "POST", body: JSON.stringify(body) }));
      setTo(null); setNote(""); setPayRef("");
      onChange?.();
    } catch (err) { setError(err instanceof ApiError ? err.message : "No se pudo completar."); }
  }
  return (
    <div className="card" style={{ background: "var(--surface-2)" }}>
      <div className="row"><strong>{fmtMoney(r.amount_cents, r.currency)}</strong><StatusBadge map={ESTADOS_DEVOLUCION} s={r.status} />
        {r.case_code && <span className="badge mono">{r.case_code}</span>}{r.contact_name && <span className="small">{r.contact_name}</span>}</div>
      <p style={{ whiteSpace: "pre-wrap" }}>{r.reason}</p>
      {r.legal_opinion && <div className="notice notice-info small"><strong>Informe jurídico ({r.legal_opinion_by})</strong>{r.legal_opinion}</div>}
      {r.decision_reason && <p className="small"><strong>Decisión de {r.decided_by}:</strong> {r.decision_reason}</p>}
      {r.totals && <p className="small muted">Cobrado y confirmado disponible para devolver: <strong>{fmtMoney(r.totals.devolvible, r.currency)}</strong></p>}
      {error && <div className="notice notice-danger" style={{ margin: "8px 0" }}>{error}</div>}
      <div className="row">
        {r.allowed?.map((a) => (
          <button key={a} className={`btn btn-sm ${a === "rechazada" ? "btn-warn" : a === "aprobada" || a === "pagada" ? "btn-primary" : ""}`} onClick={() => setTo(a)}>
            {legalStep ? "Emitir informe y devolver a revisión" : label(ACCION_DEVOLUCION, a)}
          </button>
        ))}
        {r.allowed?.length === 0 && r.status !== "pagada" && <span className="small muted">Sin acciones para su perfil en este estado.</span>}
      </div>
      {to && (
        <form className="stack" style={{ marginTop: 10 }} onSubmit={go}>
          <label className="field">{legalStep ? "Informe jurídico (orienta; la decisión es de Contabilidad)" : to === "pagada" ? "Observaciones (opcional)" : "Motivo"}
            <textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} required={to !== "pagada" && !(to === "en_revision" && r.status === "registrada") && !(to === "en_revision" && r.status === "en_revision")} />
          </label>
          {to === "pagada" && (
            <div className="form-grid">
              <label className="field">Cómo se devuelve
                <select value={payMethod} onChange={(e) => setPayMethod(e.target.value)}>
                  {["transferencia", "bizum", "tarjeta"].map((m) => <option key={m} value={m}>{label(METODOS_COBRO, m)}</option>)}
                </select>
              </label>
              <label className="field">Referencia del pago<input value={payRef} onChange={(e) => setPayRef(e.target.value)} required /></label>
            </div>
          )}
          <div className="row"><button className="btn btn-sm btn-primary">Confirmar</button><button type="button" className="btn btn-sm" onClick={() => setTo(null)}>Cancelar</button></div>
        </form>
      )}
      {r.events && (
        <details style={{ marginTop: 10 }}><summary className="small">Historial ({r.events.length})</summary>
          <ul className="small">{r.events.map((e, i) => <li key={i}>{fmtDateTime(e.at)} · {e.actor} · {label(ESTADOS_DEVOLUCION, e.to)}{e.note ? ` — ${e.note}` : ""}</li>)}</ul>
        </details>
      )}
    </div>
  );
}

/** Pestaña económica del expediente. */
export function CaseEconomy({ caseId }: { caseId: string }) {
  const [d, setD] = useState<CaseEco | null>(null);
  const [hidden, setHidden] = useState(false);
  const [mode, setMode] = useState<"" | "charge" | "pay" | "refund">("");
  const [msg, setMsg] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const load = useCallback(() => api<CaseEco>(`/economy/cases/${caseId}`).then(setD).catch(() => setHidden(true)), [caseId]);
  useEffect(() => { load(); }, [load]);
  if (hidden || !d) return null;
  const cur = d.currency;
  const done = (m: string) => { setMsg(m); setMode(""); load(); };
  return (
    <section className="card" aria-label="Economía del expediente">
      <div className="row">
        <h2 style={{ margin: 0 }}>Economía</h2>
        <span className="spacer" />
        {d.can.charge && <button className="btn btn-sm" onClick={() => setMode(mode === "charge" ? "" : "charge")}>+ Importe pactado</button>}
        {d.can.pay && <button className="btn btn-sm" onClick={() => setMode(mode === "pay" ? "" : "pay")}>+ Cobro</button>}
        {d.can.refund && <button className="btn btn-sm" onClick={() => setMode(mode === "refund" ? "" : "refund")}>Solicitar devolución</button>}
      </div>
      <p className="small muted">{d.aviso}</p>
      {msg && <div className="notice notice-ok" role="status">{msg}</div>}
      <div className="grid grid-3" style={{ margin: "10px 0" }}>
        <div className="stat"><div className="stat-label">Pactado</div><strong>{fmtMoney(d.totals.cargado, cur)}</strong></div>
        <div className="stat"><div className="stat-label">Cobrado</div><strong>{fmtMoney(d.totals.cobrado, cur)}</strong>
          <div className="small muted">{fmtMoney(d.totals.cobrado_confirmado, cur)} confirmado</div></div>
        <div className="stat"><div className="stat-label">Pendiente de cobro</div><strong style={{ color: d.totals.pendiente > 0 ? "var(--danger)" : undefined }}>{fmtMoney(d.totals.pendiente, cur)}</strong>
          {d.totals.devuelto > 0 && <div className="small muted">Devuelto: {fmtMoney(d.totals.devuelto, cur)}</div>}</div>
      </div>
      {mode === "charge" && <ChargeForm caseId={caseId} onDone={done} />}
      {mode === "pay" && <PaymentForm caseId={caseId} branches={d.branches} onDone={done} />}
      {mode === "refund" && <RefundRequestForm caseId={caseId} onDone={done} />}
      <div className="table-wrap" style={{ marginTop: 10 }}>
        <table className="data">
          <thead><tr><th>Fecha</th><th>Movimiento</th><th>Importe</th><th>Estado</th></tr></thead>
          <tbody>
            {d.charges.map((c) => (
              <tr key={c.id}><td>{c.due_date ? `Vence ${fmtDate(c.due_date)}` : "—"}</td>
                <td>{label(TIPOS_CARGO, c.kind)} · {c.concept}<div className="small muted">{c.created_by}{c.cancel_reason ? ` · anulado: ${c.cancel_reason}` : ""}</div></td>
                <td>{fmtMoney(c.amount_cents, cur)}</td><td><StatusBadge map={{ vigente: "Pactado", anulado: "Anulado" }} s={c.status} /></td></tr>
            ))}
            {d.payments.map((x) => (
              <tr key={x.id}><td>{fmtDateTime(x.received_at)}</td>
                <td>Cobro · {label(METODOS_COBRO, x.method)}{x.branch ? ` · ${x.branch}` : ""}{x.reference ? ` · ${x.reference}` : ""}
                  <div className="small muted">{x.registered_by}{x.invoice_ref ? ` · factura ${x.invoice_ref}` : ""}</div></td>
                <td>{fmtMoney(x.amount_cents, cur)}</td><td><StatusBadge map={ESTADOS_COBRO} s={x.status} /></td></tr>
            ))}
            {d.refunds.map((r) => (
              <tr key={r.id} className="clickable" onClick={() => setOpen(open === r.id ? null : r.id)}>
                <td>{fmtDateTime(r.created_at)}</td><td>Devolución solicitada<div className="small muted">{r.reason.slice(0, 80)}</div></td>
                <td>−{fmtMoney(r.amount_cents, cur)}</td><td><StatusBadge map={ESTADOS_DEVOLUCION} s={r.status} /></td></tr>
            ))}
            {d.charges.length + d.payments.length + d.refunds.length === 0 && <tr><td colSpan={4} className="empty">Sin movimientos económicos.</td></tr>}
          </tbody>
        </table>
      </div>
      {open && <RefundDetail id={open} onChange={load} />}
    </section>
  );
}

function ChargeForm({ caseId, onDone }: { caseId: string; onDone: (m: string) => void }) {
  const [kind, setKind] = useState("honorarios");
  const [concept, setConcept] = useState("");
  const [amount, setAmount] = useState("");
  const [due, setDue] = useState("");
  const [error, setError] = useState<string | null>(null);
  async function submit(e: React.FormEvent) {
    e.preventDefault(); setError(null);
    const cents = parseMoney(amount);
    if (!cents) return;
    try {
      await api(`/economy/cases/${caseId}/charges`, { method: "POST", body: JSON.stringify({ kind, concept, amount_cents: cents, due_date: due || null }) });
      onDone(`Importe pactado de ${fmtMoney(cents)} registrado.`);
    } catch (err) { setError(err instanceof ApiError ? err.message : "No se pudo registrar."); }
  }
  return (
    <form className="form-grid" onSubmit={submit} aria-label="Importe pactado">
      {error && <div className="notice notice-danger full">{error}</div>}
      <label className="field">Tipo
        <select value={kind} onChange={(e) => setKind(e.target.value)}>
          {Object.entries(TIPOS_CARGO).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </label>
      <MoneyInput label="Importe (lo indica usted; el sistema no calcula honorarios)" value={amount} onChange={setAmount} />
      <label className="field">Concepto<input value={concept} onChange={(e) => setConcept(e.target.value)} minLength={3} required placeholder="p. ej. Hoja de encargo, primer plazo" /></label>
      <label className="field">Vencimiento <span className="hint">opcional</span><input type="date" value={due} onChange={(e) => setDue(e.target.value)} /></label>
      <div className="full"><button className="btn btn-primary">Guardar importe</button></div>
    </form>
  );
}

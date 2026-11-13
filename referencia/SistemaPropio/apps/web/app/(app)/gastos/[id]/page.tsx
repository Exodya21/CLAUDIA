"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { MoneyInput, StatusBadge } from "@/components/economy";
import { api, ApiError, fieldErrors, type ExpenseCatalog, type ExpenseRow } from "@/lib/api";
import { ESTADOS_GASTO, FORMAS_PAGO_GASTO, centsToInput, fmtDateTime, fmtMoney, label, parseMoney } from "@/lib/format";

interface Detail extends ExpenseRow {
  events: { from: string | null; to: string; note: string | null; actor: string; at: string }[];
  ocr: { engine: string | null; suggestion: { fields?: Record<string, { value: string | number; confidence: string }>; message?: string | null }; text: string };
  allowed: { edit: boolean; submit: boolean; review: boolean; annul: boolean; reconcile: boolean };
  duplicate_of: string | null;
}

const CONF: Record<string, string> = { alta: "badge-green", media: "badge-yellow", baja: "badge-red" };

function GastoInner() {
  const { id } = useParams<{ id: string }>();
  const nuevo = useSearchParams().get("nuevo");
  const [e, setE] = useState<Detail | null>(null);
  const [cat, setCat] = useState<ExpenseCatalog | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(nuevo ? "Justificante leído. Revise los datos propuestos, complete lo que falte y envíelo." : null);
  const load = useCallback(() => api<Detail>(`/expenses/${id}`).then(setE).catch((x) => setError(x instanceof ApiError ? x.message : "Error")), [id]);
  useEffect(() => { load(); api<ExpenseCatalog>("/expenses/catalog").then(setCat).catch(() => undefined); }, [load]);
  if (error && !e) return <div className="notice notice-danger">{error} <Link href="/gastos">Volver</Link></div>;
  if (!e || !cat) return <p className="muted">Cargando…</p>;
  const receiptUrl = `/api/v1/expenses/${e.id}/receipt`;
  return (
    <div className="stack">
      <div className="topline">
        <div>
          <p className="small"><Link href="/gastos">← Gastos</Link></p>
          <h1>{e.supplier_name ?? "Gasto sin proveedor"}</h1>
          <div className="row"><StatusBadge map={ESTADOS_GASTO} s={e.status} /><span>{e.employee}</span><span className="muted small">{e.branch}</span>
            {e.amount_cents !== null && <strong>{fmtMoney(e.amount_cents, e.currency)}</strong>}</div>
        </div>
      </div>
      {msg && <div className="notice notice-ok" role="status">{msg}</div>}
      {error && <div className="notice notice-danger">{error}</div>}
      {e.duplicate_of && <div className="notice notice-warn">Atención: hay otro gasto con el mismo justificante. <Link href={`/gastos/${e.duplicate_of}`}>Ver</Link></div>}
      {e.status === "devuelto" && e.review_note && <div className="notice notice-warn"><strong>Contabilidad lo ha devuelto</strong>{e.review_note}</div>}

      <div className="grid grid-2">
        <div className="card">
          <h2 style={{ marginTop: 0 }}>Justificante</h2>
          {e.receipt_mime?.startsWith("image/") ? (
            // eslint-disable-next-line @next/next/no-img-element
            <a href={receiptUrl} target="_blank" rel="noreferrer"><img src={receiptUrl} alt="Justificante del gasto" style={{ maxWidth: "100%", border: "1px solid var(--line)", borderRadius: 8 }} /></a>
          ) : e.has_receipt ? <a className="btn" href={receiptUrl} target="_blank" rel="noreferrer">Abrir el PDF</a> : <p className="muted">Sin justificante.</p>}
          <p className="small muted">{e.receipt_name} · consultar el justificante queda registrado.</p>
          <details>
            <summary className="small">Texto leído ({e.ocr.engine === "ninguno" ? "lectura no disponible" : e.ocr.engine})</summary>
            <pre className="small" style={{ whiteSpace: "pre-wrap", maxHeight: 260, overflow: "auto" }}>{e.ocr.text || e.ocr.suggestion.message || "—"}</pre>
          </details>
        </div>
        {e.allowed.edit ? <EditForm e={e} cat={cat} onSaved={(d, m) => { setE(d); setMsg(m); setError(null); }} onError={setError} />
          : <ReadOnly e={e} cat={cat} />}
      </div>

      {(e.allowed.review || e.allowed.annul || e.allowed.reconcile) && <Review e={e} onDone={(d, m) => { setE(d); setMsg(m); setError(null); }} onError={setError} />}

      <div className="card">
        <h2 style={{ marginTop: 0 }}>Historial</h2>
        <ul className="small">{e.events.map((x, i) => <li key={i}>{fmtDateTime(x.at)} · {x.actor} · {label(ESTADOS_GASTO, x.to)}{x.note ? ` — ${x.note}` : ""}</li>)}</ul>
      </div>
    </div>
  );
}

function ReadOnly({ e, cat }: { e: Detail; cat: ExpenseCatalog }) {
  return (
    <div className="card">
      <h2 style={{ marginTop: 0 }}>Datos</h2>
      <dl className="kv">
        <dt>Fecha</dt><dd>{e.expense_date?.split("-").reverse().join("/") ?? "—"}</dd>
        <dt>Proveedor</dt><dd>{e.supplier_name ?? "—"} {e.supplier_tax_id && <span className="mono small">({e.supplier_tax_id})</span>}</dd>
        <dt>Concepto</dt><dd>{e.category ? cat.categories[e.category] : "—"}</dd>
        <dt>Descripción</dt><dd>{e.description ?? "—"}</dd>
        <dt>Total</dt><dd>{fmtMoney(e.amount_cents, e.currency)}</dd>
        <dt>IVA (según justificante)</dt><dd>{fmtMoney(e.vat_cents, e.currency)}</dd>
        <dt>Forma de pago</dt><dd>{e.payment_method ? label(FORMAS_PAGO_GASTO, e.payment_method) : "—"}{e.card ? ` · ${e.card}` : ""}</dd>
        <dt>Sede</dt><dd>{e.branch}</dd>
        {e.reviewed_by && <><dt>Revisado por</dt><dd>{e.reviewed_by}</dd></>}
        {e.reconcile_ref && <><dt>Conciliación</dt><dd>{e.reconcile_ref}</dd></>}
      </dl>
    </div>
  );
}

function EditForm({ e, cat, onSaved, onError }: { e: Detail; cat: ExpenseCatalog; onSaved: (d: Detail, m: string) => void; onError: (m: string) => void }) {
  const sug = e.ocr.suggestion.fields ?? {};
  const org = cat.organizations.find((o) => o.id === e.organization_id);
  const [f, setF] = useState({
    expense_date: e.expense_date ?? "", supplier_name: e.supplier_name ?? "", supplier_tax_id: e.supplier_tax_id ?? "",
    category: e.category ?? "", description: e.description ?? "", amount: centsToInput(e.amount_cents), vat: centsToInput(e.vat_cents),
    payment_method: e.payment_method ?? "", card_id: e.card_id ?? "", branch_id: e.branch_id,
  });
  const [fe, setFe] = useState<Record<string, string>>({});
  const set = (k: keyof typeof f, v: string) => setF({ ...f, [k]: v });
  const conf = (k: string) => sug[k] ? <span className={`badge ${CONF[sug[k].confidence] ?? ""}`} title="Propuesto por la lectura automática">leído · confianza {sug[k].confidence}</span> : null;
  const cards = cat.my_cards.filter((c) => c.organization_id === e.organization_id);

  async function save(andSubmit: boolean) {
    setFe({});
    const amount = f.amount ? parseMoney(f.amount) : null;
    const vat = f.vat ? parseMoney(f.vat) : null;
    if ((f.amount && amount === null) || (f.vat && vat === null)) { onError("Revise los importes (ej. 12,50)."); return; }
    try {
      let d = await api<Detail>(`/expenses/${e.id}`, { method: "PATCH", body: JSON.stringify({
        expense_date: f.expense_date || null, supplier_name: f.supplier_name || null, supplier_tax_id: f.supplier_tax_id || null,
        category: f.category || null, description: f.description || null, amount_cents: amount, vat_cents: vat,
        payment_method: f.payment_method || null, card_id: f.payment_method === "tarjeta_empresa" ? f.card_id || null : null,
        branch_id: f.branch_id, version: e.version }) });
      if (andSubmit) d = await api<Detail>(`/expenses/${e.id}/submit`, { method: "POST" });
      onSaved(d, andSubmit ? "Gasto enviado a Contabilidad." : "Cambios guardados.");
    } catch (err) { setFe(fieldErrors(err)); onError(err instanceof ApiError ? err.message : "No se pudo guardar."); }
  }
  return (
    <form className="card" onSubmit={(ev) => { ev.preventDefault(); save(true); }} aria-label="Datos del gasto">
      <h2 style={{ marginTop: 0 }}>Revise y confirme</h2>
      {e.ocr.suggestion.message && <div className="notice notice-warn small">{e.ocr.suggestion.message}</div>}
      <div className="form-grid">
        <label className="field">Fecha {conf("expense_date")}<input type="date" value={f.expense_date} onChange={(x) => set("expense_date", x.target.value)} required /></label>
        <label className="field">Proveedor {conf("supplier_name")}<input value={f.supplier_name} onChange={(x) => set("supplier_name", x.target.value)} required /></label>
        <label className="field">NIF/CIF del proveedor {conf("supplier_tax_id")}<input value={f.supplier_tax_id} onChange={(x) => set("supplier_tax_id", x.target.value)} /></label>
        <label className="field">Concepto
          <select value={f.category} onChange={(x) => set("category", x.target.value)} required>
            <option value="">Elija…</option>{Object.entries(cat.categories).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <div>{conf("amount_cents")}<MoneyInput label="Total pagado" value={f.amount} onChange={(v) => set("amount", v)} error={fe.amount_cents} /></div>
        <label className="field">IVA (cuota del ticket) {conf("vat_cents")}
          <input inputMode="decimal" placeholder="0,00" value={f.vat} onChange={(x) => set("vat", x.target.value)} className={fe.vat_cents ? "invalid" : undefined} />
        </label>
        <label className="field">Forma de pago
          <select value={f.payment_method} onChange={(x) => set("payment_method", x.target.value)} required>
            <option value="">Elija…</option>
            {Object.entries(FORMAS_PAGO_GASTO).filter(([k]) => k !== "tarjeta_empresa" || cards.length > 0).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        {f.payment_method === "tarjeta_empresa" ? (
          <label className="field">Tarjeta
            <select value={f.card_id} onChange={(x) => set("card_id", x.target.value)} required>
              <option value="">Elija…</option>{cards.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
            </select>
          </label>
        ) : (
          <label className="field">Sede {f.payment_method === "efectivo_caja" && <span className="hint">se descuenta de esta caja</span>}
            <select value={f.branch_id} onChange={(x) => set("branch_id", x.target.value)}>{org?.branches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}</select>
          </label>
        )}
        <label className="field full">Descripción <span className="hint">para qué fue (p. ej. desplazamiento al juzgado, expediente…)</span>
          <input value={f.description} onChange={(x) => set("description", x.target.value)} maxLength={500} />
        </label>
      </div>
      <p className="small muted">Los datos marcados como «leído» los ha propuesto el sistema: compruébelos con el ticket antes de enviar.</p>
      <div className="row">
        <button className="btn btn-primary">Confirmar y enviar a Contabilidad</button>
        <button type="button" className="btn" onClick={() => save(false)}>Guardar borrador</button>
      </div>
    </form>
  );
}

function Review({ e, onDone, onError }: { e: Detail; onDone: (d: Detail, m: string) => void; onError: (m: string) => void }) {
  const [note, setNote] = useState("");
  const [ref, setRef] = useState("");
  async function act(action: "aprobar" | "devolver" | "anular") {
    try { onDone(await api<Detail>(`/expenses/${e.id}/review`, { method: "POST", body: JSON.stringify({ action, note: note || null }) }),
      { aprobar: "Gasto aprobado.", devolver: "Gasto devuelto a la persona.", anular: "Gasto anulado." }[action]); setNote(""); }
    catch (err) { onError(err instanceof ApiError ? err.message : "Error"); }
  }
  async function reconcile() {
    try { onDone(await api<Detail>(`/expenses/${e.id}/reconcile`, { method: "POST", body: JSON.stringify({ reference: ref }) }), "Gasto conciliado."); }
    catch (err) { onError(err instanceof ApiError ? err.message : "Error"); }
  }
  return (
    <div className="card">
      <h2 style={{ marginTop: 0 }}>{e.status === "borrador" ? "Descartar" : "Revisión de Contabilidad"}</h2>
      {(e.allowed.review || e.allowed.annul) && (
        <div className="stack">
          <label className="field">Motivo <span className="hint">obligatorio para devolver o anular</span>
            <input value={note} onChange={(x) => setNote(x.target.value)} placeholder="p. ej. Falta el NIF del proveedor" />
          </label>
          <div className="row">
            {e.allowed.review && <button className="btn btn-primary" onClick={() => act("aprobar")}>Aprobar</button>}
            {e.allowed.review && <button className="btn" onClick={() => act("devolver")}>Devolver para corregir</button>}
            {e.allowed.annul && <button className="btn btn-warn" onClick={() => act("anular")}>{e.status === "borrador" ? "Descartar borrador" : "Anular"}</button>}
          </div>
          {e.allowed.review && e.payment_method === "efectivo_caja" && <p className="small muted">Pagado con la caja de la sede: al aprobarlo queda conciliado con ella.</p>}
        </div>
      )}
      {e.allowed.reconcile && e.payment_method === "personal" && (
        <div className="row" style={{ marginTop: 10 }}>
          <input aria-label="Referencia del reembolso" placeholder="Referencia del reembolso (transferencia o nómina)" value={ref} onChange={(x) => setRef(x.target.value)} style={{ flex: 1 }} />
          <button className="btn btn-primary" onClick={reconcile}>Marcar reembolsado</button>
        </div>
      )}
      {e.allowed.reconcile && e.payment_method === "tarjeta_empresa" && <p className="small">Se concilia desde <Link href="/gastos">Tarjetas y extractos</Link> al importar el extracto del banco.</p>}
    </div>
  );
}

export default function Gasto() {
  return <Suspense fallback={<p className="muted">Cargando…</p>}><GastoInner /></Suspense>;
}

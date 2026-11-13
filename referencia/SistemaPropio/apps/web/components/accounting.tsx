"use client";

// Contabilidad F5.4: proveedores y facturas recibidas, tesorería con remesas de doble firma y cierre del mes.
import { useCallback, useEffect, useMemo, useState } from "react";
import { MoneyInput } from "@/components/economy";
import { api, ApiError, fieldErrors, postForm } from "@/lib/api";
import { fmtDate, fmtDateTime, fmtMoney, parseMoney } from "@/lib/format";

const errMsg = (e: unknown) => (e instanceof ApiError ? e.message : "No se ha podido completar la operación.");
const CATS: Record<string, string> = {
  alquiler: "Alquiler", suministros: "Suministros", software: "Software y licencias", telefonia: "Telefonía e internet",
  gestoria: "Gestoría y asesoría", marketing: "Marketing", material: "Material de oficina", limpieza: "Limpieza",
  seguros: "Seguros", tasas: "Tasas y suplidos", formacion: "Formación", otros: "Otros",
};
const ACTS: Record<string, string> = { laboral: "Laboral", extranjeria: "Extranjería", compartida: "Compartida", sin_asignar: "Sin asignar" };
const INV_ST: Record<string, [string, string]> = {
  recibida: ["Por validar", "badge-yellow"], validada: ["Validada", "badge-blue"], programada: ["En remesa autorizada", "badge-blue"],
  pagada: ["Pagada", "badge-green"], rechazada: ["Rechazada", "badge-red"],
};
const BATCH_ST: Record<string, [string, string]> = {
  propuesta: ["Pendiente de firmas", "badge-yellow"], autorizada: ["Autorizada", "badge-blue"], enviada: ["Subida al banco", "badge-green"],
  rechazada: ["No autorizada", "badge-red"], anulada: ["Anulada", ""],
};
const madridDay = (d: Date) => d.toLocaleDateString("sv-SE", { timeZone: "Europe/Madrid" });
const toTxt = (c: number | undefined | null) => (typeof c === "number" ? (c / 100).toFixed(2).replace(".", ",") : "");

interface Supplier { id: string; name: string; tax_id: string; iban_masked: string | null; category: string; category_label: string; activity: string; branch: string | null; branch_id: string | null; payment_terms_days: number | null; recurring: boolean; active: boolean; pending_cents: number; version: number }
interface Invoice { id: string; supplier_id: string; supplier: string; number: string; issue_date: string; due_date: string | null; base_cents: number; vat_cents: number; withholding_cents: number; total_cents: number; currency: string; category: string; category_label: string; activity: string; branch: string | null; status: string; overdue: boolean; batch: { code: string; status: string } | null; version: number; rejected_reason: string | null; paid_at: string | null; validated_by: string | null; registered_by: string }
interface Branch { id: string; name: string }

// ------------------------------------------------------------------ proveedores y facturas
export function InvoicesPanel({ orgId, canRegister, canValidate, canSuppliers, branches }: { orgId: string; canRegister: boolean; canValidate: boolean; canSuppliers: boolean; branches: Branch[] }) {
  const [status, setStatus] = useState("pendientes");
  const [rows, setRows] = useState<Invoice[] | null>(null);
  const [sups, setSups] = useState<Supplier[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const load = useCallback(() => {
    api<Invoice[]>(`/accounting/invoices?organization_id=${orgId}&status=${status}`).then(setRows).catch((e) => setErr(errMsg(e)));
    api<Supplier[]>(`/accounting/suppliers?organization_id=${orgId}`).then(setSups).catch(() => setSups([]));
  }, [orgId, status]);
  useEffect(() => { load(); }, [load]);
  return (
    <div className="stack">
      {msg && <div className="notice notice-ok" role="status">{msg}</div>}
      {canRegister && <NewInvoice orgId={orgId} sups={sups} branches={branches} canValidate={canValidate} canSuppliers={canSuppliers}
        onDone={(t) => { setMsg(t); load(); }} />}
      <div className="card">
        <div className="row"><h2 style={{ margin: 0 }}>Facturas recibidas</h2><span className="spacer" />
          <select aria-label="Estado de las facturas" value={status} onChange={(e) => setStatus(e.target.value)} style={{ width: "auto" }}>
            <option value="pendientes">Pendientes de pagar</option><option value="recibida">Por validar</option><option value="validada">Validadas</option>
            <option value="programada">En remesa</option><option value="pagada">Pagadas</option><option value="rechazada">Rechazadas</option><option value="todas">Todas</option>
          </select></div>
        {err && <div className="notice notice-danger">{err}</div>}
        <div className="table-wrap" style={{ marginTop: 10 }}>
          <table className="data">
            <thead><tr><th>Proveedor</th><th>Factura</th><th>Vence</th><th style={{ textAlign: "right" }}>Total</th><th>Actividad</th><th>Estado</th><th></th></tr></thead>
            <tbody>
              {rows?.length === 0 && <tr><td colSpan={7} className="empty">No hay facturas en esta vista.</td></tr>}
              {rows?.map((x) => <InvoiceRow key={x.id} x={x} canValidate={canValidate} branches={branches} onDone={(t) => { setMsg(t); load(); }} />)}
            </tbody>
          </table>
        </div>
      </div>
      <Suppliers orgId={orgId} sups={sups} canManage={canSuppliers} branches={branches} onDone={load} />
    </div>
  );
}

function InvoiceRow({ x, canValidate, branches, onDone }: { x: Invoice; canValidate: boolean; branches: Branch[]; onDone: (t: string) => void }) {
  const [open, setOpen] = useState(false);
  const [act, setAct] = useState(x.activity);
  const [branch, setBranch] = useState("");
  const [reason, setReason] = useState("");
  const [err, setErr] = useState<string | null>(null);
  async function decide(approve: boolean) {
    setErr(null);
    try {
      await api(`/accounting/invoices/${x.id}/decide`, { method: "POST", body: JSON.stringify({ version: x.version, approve, reason: reason || null, activity: act, branch_id: branch || null }) });
      onDone(approve ? `Factura ${x.number} validada.` : `Factura ${x.number} rechazada.`);
    } catch (e) { setErr(errMsg(e)); }
  }
  return (
    <>
      <tr>
        <td>{x.supplier}<div className="small muted">{x.category_label}{x.branch ? ` · ${x.branch}` : ""}</div></td>
        <td><a href={`/api/v1/accounting/invoices/${x.id}/file`} target="_blank" rel="noreferrer" className="mono">{x.number}</a><div className="small muted">{fmtDate(x.issue_date)}</div></td>
        <td>{x.due_date ? fmtDate(x.due_date) : "—"}{x.overdue && <div><span className="badge badge-red">Vencida</span></div>}</td>
        <td style={{ textAlign: "right" }}><strong>{fmtMoney(x.total_cents, x.currency)}</strong><div className="small muted">base {fmtMoney(x.base_cents, x.currency)} · IVA {fmtMoney(x.vat_cents, x.currency)}{x.withholding_cents ? ` · ret. ${fmtMoney(x.withholding_cents, x.currency)}` : ""}</div></td>
        <td>{ACTS[x.activity]}</td>
        <td><span className={`badge ${INV_ST[x.status][1]}`}>{INV_ST[x.status][0]}</span>{x.batch && <div className="small mono">{x.batch.code}</div>}{x.paid_at && <div className="small muted">el {fmtDate(x.paid_at)}</div>}{x.rejected_reason && <div className="small muted">{x.rejected_reason}</div>}</td>
        <td>{canValidate && x.status === "recibida" && <button className="btn btn-sm" onClick={() => setOpen(!open)}>Revisar</button>}</td>
      </tr>
      {open && (
        <tr><td colSpan={7}>
          <div className="row" aria-label={`Revisar factura ${x.number}`}>
            <label className="field" style={{ width: 160 }}>Actividad<select value={act} onChange={(e) => setAct(e.target.value)}>{["laboral", "extranjeria", "compartida"].map((a) => <option key={a} value={a}>{ACTS[a]}</option>)}</select></label>
            <label className="field" style={{ width: 160 }}>Oficina<select value={branch} onChange={(e) => setBranch(e.target.value)}><option value="">{x.branch ?? "Sin oficina"}</option>{branches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}</select></label>
            <button className="btn btn-sm btn-primary" onClick={() => decide(true)}>Validar</button>
            <input aria-label="Motivo del rechazo" placeholder="Motivo si se rechaza" value={reason} onChange={(e) => setReason(e.target.value)} style={{ maxWidth: 240 }} />
            <button className="btn btn-sm" onClick={() => decide(false)}>Rechazar</button>
            {err && <span className="error-text small">{err}</span>}
          </div>
        </td></tr>
      )}
    </>
  );
}

interface ReadRes { proposal: Record<string, string | number | boolean | string[]>; supplier: Supplier | null; duplicate_file: Invoice | null }
function NewInvoice({ orgId, sups, branches, canValidate, canSuppliers, onDone }: { orgId: string; sups: Supplier[]; branches: Branch[]; canValidate: boolean; canSuppliers: boolean; onDone: (t: string) => void }) {
  const [queue, setQueue] = useState<File[]>([]);  // varias facturas: se leen una tras otra
  const file = queue[0] ?? null;
  const [read, setRead] = useState<ReadRes | null>(null);
  const [done, setDone] = useState(0);
  const [f, setF] = useState({ supplier_id: "", number: "", issue: "", due: "", base: "", vat: "", wh: "", total: "", category: "otros", activity: "compartida", branch: "", description: "", validate: canValidate });
  const [dups, setDups] = useState<Invoice[] | null>(null);
  const [created, setCreated] = useState<Supplier[]>([]);
  const [fileKey, setFileKey] = useState(0);
  const all = [...sups, ...created.filter((c) => !sups.some((s) => s.id === c.id))];
  const [reason, setReason] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [fe, setFe] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof f) => (v: string | boolean) => setF((o) => ({ ...o, [k]: v }));
  useEffect(() => { if (file && !read) doRead(file); }, [file]);  // eslint-disable-line react-hooks/exhaustive-deps
  function next() { setRead(null); setDups(null); setReason(""); setErr(null); setQueue((q) => q.slice(1)); }
  async function doRead(fl: File) {
    setErr(null); setBusy(true);
    const fd = new FormData(); fd.append("organization_id", orgId); fd.append("file", fl);
    try {
      const r = await postForm<ReadRes>("/accounting/invoices/read", fd);
      setRead(r);
      const p = r.proposal;
      setF((o) => ({ ...o, supplier_id: r.supplier?.id ?? "", number: String(p.numero ?? ""), issue: String(p.fecha ?? ""), due: String(p.vencimiento ?? ""),
        base: toTxt(p.base_cents as number), vat: toTxt(p.iva_cents as number), wh: toTxt(p.retencion_cents as number), total: toTxt(p.total_cents as number),
        category: r.supplier?.category ?? o.category, activity: r.supplier?.activity ?? o.activity, branch: r.supplier?.branch_id ?? "" }));
    } catch (e) { setErr(errMsg(e)); } finally { setBusy(false); }
  }
  const sum = (parseMoney(f.base) ?? 0) + (parseMoney(f.vat) ?? 0) - (parseMoney(f.wh) ?? 0);
  const totalOk = f.total !== "" && parseMoney(f.total) === sum;
  async function save(e: React.FormEvent) {
    e.preventDefault(); setErr(null); setFe({});
    const data = { organization_id: orgId, supplier_id: f.supplier_id, number: f.number, issue_date: f.issue, due_date: f.due || null,
      base_cents: parseMoney(f.base), vat_cents: parseMoney(f.vat) ?? 0, withholding_cents: parseMoney(f.wh) ?? 0, total_cents: parseMoney(f.total),
      category: f.category, activity: f.activity, branch_id: f.branch || null, description: f.description || null, validate_now: f.validate,
      duplicate_reason: dups ? reason : null };
    const fd = new FormData(); fd.append("data", JSON.stringify(data)); fd.append("file", file!);
    setBusy(true);
    try {
      const x = await postForm<Invoice>("/accounting/invoices", fd);
      onDone(`Factura ${x.number} de ${x.supplier} registrada (${INV_ST[x.status][0].toLowerCase()}).`);
      setDone((d) => d + 1);
      if (queue.length <= 1) setFileKey((k) => k + 1);
      next();
    } catch (ex) {
      if (ex instanceof ApiError && ex.body.code === "posible_duplicado") setDups(ex.body.details as Invoice[]);
      else { setErr(errMsg(ex)); setFe(fieldErrors(ex)); }
    } finally { setBusy(false); }
  }
  return (
    <div className="card stack" style={{ gap: 10 }}>
      <h2 style={{ margin: 0 }}>Registrar factura recibida</h2>
      <div className="row">
        <input key={fileKey} type="file" multiple aria-label="Factura (PDF o imagen)" accept=".pdf,.jpg,.jpeg,.png" onChange={(e) => { setRead(null); setDone(0); setQueue(Array.from(e.target.files ?? [])); }} style={{ maxWidth: 340 }} />
        <button className="btn btn-sm" disabled={!file || busy} onClick={() => file && doRead(file)}>{busy ? "Leyendo…" : "Leer factura"}</button>
        {queue.length > 1 && <span className="badge badge-blue">Factura {done + 1} de {done + queue.length}: {file?.name}</span>}
        {file && <button type="button" className="btn btn-sm" onClick={next} disabled={busy}>Saltar esta</button>}
        <span className="small muted">Puede seleccionar varias facturas: se leen solas una tras otra y usted solo comprueba y registra. El IVA es el que figura en la factura: el sistema no lo calcula.</span>
      </div>
      {err && <div className="notice notice-danger" role="alert">{err}</div>}
      {read && (
        <form className="stack" style={{ gap: 10 }} onSubmit={save} aria-label="Datos de la factura">
          {read.duplicate_file && <div className="notice notice-danger">Este archivo ya está registrado: factura {read.duplicate_file.number} de {read.duplicate_file.supplier}.</div>}
          <p className="small" style={{ margin: 0 }}>Lectura: confianza <strong>{String(read.proposal.confianza ?? "baja")}</strong>{read.proposal.cuadra === false ? " · ¡base + IVA − retención no da el total leído!" : ""}{read.proposal.cif && !read.supplier ? ` · CIF ${read.proposal.cif} sin proveedor dado de alta` : ""}{read.proposal.origen === "ocr" ? " · leída como imagen (escaneada)" : ""}{read.proposal.aviso ? ` · ${String(read.proposal.aviso)}` : ""}</p>
          {Array.isArray(read.proposal.deducido) && read.proposal.deducido.includes("base_imponible") && <div className="notice notice-warn small">La base imponible no se leía bien y se ha deducido del total, el IVA y la retención impresos (encajan entre sí). <b>Compruébela con la factura.</b></div>}
          {!read.supplier && read.proposal.cif && canSuppliers && <QuickSupplier orgId={orgId} cif={String(read.proposal.cif)} cifs={Array.isArray(read.proposal.cif_candidatos) ? read.proposal.cif_candidatos : [String(read.proposal.cif)]} name0={read.proposal.proveedor_nombre ? String(read.proposal.proveedor_nombre) : ""} iban={read.proposal.iban ? String(read.proposal.iban) : ""} onCreated={(s) => { setCreated((c) => [...c, s]); setRead((r) => (r ? { ...r, supplier: s } : r)); set("supplier_id")(s.id); set("category")(s.category); }} />}
          <div className="form-grid">
            <label className="field">Proveedor *<select key={all.length} value={f.supplier_id} onChange={(e) => { const s = all.find((x) => x.id === e.target.value); set("supplier_id")(e.target.value); if (s) { set("category")(s.category); set("activity")(s.activity); } }} required>
              <option value="">Elija…</option>{all.filter((s) => s.active).map((s) => <option key={s.id} value={s.id}>{s.name} · {s.tax_id}</option>)}</select>{fe.supplier_id && <span className="error-text">{fe.supplier_id}</span>}</label>
            <label className="field">Número *<input value={f.number} onChange={(e) => set("number")(e.target.value)} required /></label>
            <label className="field">Fecha de la factura *<input type="date" value={f.issue} onChange={(e) => set("issue")(e.target.value)} required /></label>
            <label className="field">Vencimiento<input type="date" value={f.due} onChange={(e) => set("due")(e.target.value)} />{fe.due_date && <span className="error-text">{fe.due_date}</span>}</label>
            <MoneyInput label="Base imponible *" value={f.base} onChange={set("base")} />
            <MoneyInput label="IVA (de la factura)" value={f.vat} onChange={set("vat")} optional />
            <MoneyInput label="Retención" value={f.wh} onChange={set("wh")} optional />
            <MoneyInput label="Total *" value={f.total} onChange={set("total")} error={fe.total_cents} />
            <p className="full small" style={{ margin: 0 }}>{totalOk ? <span className="badge badge-green">Base + IVA − retención = total</span> : <span className="badge badge-red">Las cifras no cuadran ({fmtMoney(sum)})</span>}</p>
            <label className="field">Centro de coste<select value={f.category} onChange={(e) => set("category")(e.target.value)}>{Object.entries(CATS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
            <label className="field">Actividad<select value={f.activity} onChange={(e) => set("activity")(e.target.value)}>{["laboral", "extranjeria", "compartida"].map((a) => <option key={a} value={a}>{ACTS[a]}</option>)}</select></label>
            <label className="field">Oficina<select value={f.branch} onChange={(e) => set("branch")(e.target.value)}><option value="">Sin oficina (general)</option>{branches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}</select></label>
            <label className="field">Descripción<input value={f.description} onChange={(e) => set("description")(e.target.value)} /></label>
            {canValidate && <label className="row small full"><input type="checkbox" style={{ width: "auto" }} checked={f.validate} onChange={(e) => set("validate")(e.target.checked)} /> He comprobado los datos con el original: registrar ya validada</label>}
          </div>
          {dups && (
            <div className="notice notice-warn" role="alert"><strong>Hay una factura parecida (mismo proveedor, importe y fecha)</strong>
              {dups.map((d) => <div key={d.id} className="small">{d.number} · {fmtMoney(d.total_cents, d.currency)} · {INV_ST[d.status][0]}</div>)}
              <label className="field" style={{ marginTop: 8 }}>Si es otra distinta, explique por qué<input value={reason} onChange={(e) => setReason(e.target.value)} minLength={10} required /></label>
            </div>
          )}
          <div><button className="btn btn-primary" disabled={busy || !totalOk}>{dups ? "Registrar de todos modos" : "Registrar factura"}</button></div>
        </form>
      )}
    </div>
  );
}

function QuickSupplier({ orgId, cif, cifs, name0, iban, onCreated }: { orgId: string; cif: string; cifs: string[]; name0: string; iban: string; onCreated: (s: Supplier) => void }) {
  const [name, setName] = useState(name0);
  const [taxId, setTaxId] = useState(cif);
  const [cat, setCat] = useState("otros");
  const [ib, setIb] = useState(iban);
  const [err, setErr] = useState<string | null>(null);
  async function create() {
    setErr(null);
    try { onCreated(await api<Supplier>("/accounting/suppliers", { method: "POST", body: JSON.stringify({ organization_id: orgId, name, tax_id: taxId, iban: ib || null, category: cat }) })); }
    catch (e) { setErr(errMsg(e)); }
  }
  return (
    <div className="notice notice-info row" aria-label="Alta rápida de proveedor">
      <span style={{ fontWeight: 700 }}>Dar de alta el proveedor</span>
      {cifs.length > 1
        ? <select aria-label="CIF del proveedor" value={taxId} onChange={(e) => setTaxId(e.target.value)} style={{ width: "auto" }} title="La factura trae varios CIF/NIF: elija el del proveedor (no el del despacho)">{cifs.map((c) => <option key={c} value={c}>{c}</option>)}</select>
        : <span className="mono">{taxId}</span>}
      <input aria-label="Nombre del proveedor" placeholder="Nombre o razón social" value={name} onChange={(e) => setName(e.target.value)} style={{ maxWidth: 240 }} />
      <select aria-label="Categoría del proveedor" value={cat} onChange={(e) => setCat(e.target.value)} style={{ width: "auto" }}>{Object.entries(CATS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
      <input aria-label="IBAN del proveedor" placeholder="IBAN (para pagarle por remesa)" value={ib} onChange={(e) => setIb(e.target.value)} style={{ maxWidth: 260 }} />
      <button type="button" className="btn btn-sm" disabled={name.length < 2} onClick={create}>Crear proveedor</button>
      {err && <span className="error-text small">{err}</span>}
    </div>
  );
}

function Suppliers({ orgId, sups, canManage, branches, onDone }: { orgId: string; sups: Supplier[]; canManage: boolean; branches: Branch[]; onDone: () => void }) {
  const [f, setF] = useState({ name: "", tax_id: "", iban: "", category: "otros", activity: "compartida", branch_id: "", terms: "", recurring: false });
  const [err, setErr] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  async function add(e: React.FormEvent) {
    e.preventDefault(); setErr(null);
    try {
      await api("/accounting/suppliers", { method: "POST", body: JSON.stringify({ organization_id: orgId, name: f.name, tax_id: f.tax_id, iban: f.iban || null, category: f.category, activity: f.activity, branch_id: f.branch_id || null, payment_terms_days: f.terms ? Number(f.terms) : null, recurring: f.recurring }) });
      setF({ name: "", tax_id: "", iban: "", category: "otros", activity: "compartida", branch_id: "", terms: "", recurring: false }); setOpen(false); onDone();
    } catch (x) { setErr(errMsg(x) + (Object.keys(fieldErrors(x)).length ? `: ${Object.values(fieldErrors(x)).join(", ")}` : "")); }
  }
  return (
    <div className="card">
      <div className="row"><h2 style={{ margin: 0 }}>Proveedores</h2><span className="spacer" />{canManage && <button className="btn btn-sm" onClick={() => setOpen(!open)}>{open ? "Cerrar" : "Nuevo proveedor"}</button>}</div>
      {open && (
        <form className="form-grid" style={{ marginTop: 10 }} onSubmit={add} aria-label="Nuevo proveedor">
          <label className="field">Nombre *<input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} required /></label>
          <label className="field">CIF/NIF *<input value={f.tax_id} onChange={(e) => setF({ ...f, tax_id: e.target.value })} required /></label>
          <label className="field">IBAN<input value={f.iban} onChange={(e) => setF({ ...f, iban: e.target.value })} /></label>
          <label className="field">Categoría<select value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })}>{Object.entries(CATS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
          <label className="field">Actividad<select value={f.activity} onChange={(e) => setF({ ...f, activity: e.target.value })}>{["laboral", "extranjeria", "compartida"].map((a) => <option key={a} value={a}>{ACTS[a]}</option>)}</select></label>
          <label className="field">Oficina<select value={f.branch_id} onChange={(e) => setF({ ...f, branch_id: e.target.value })}><option value="">General</option>{branches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}</select></label>
          <label className="field">Días de pago<input inputMode="numeric" value={f.terms} onChange={(e) => setF({ ...f, terms: e.target.value })} /></label>
          <label className="row small"><input type="checkbox" style={{ width: "auto" }} checked={f.recurring} onChange={(e) => setF({ ...f, recurring: e.target.checked })} /> Factura todos los meses</label>
          {err && <div className="full notice notice-danger">{err}</div>}
          <div className="full"><button className="btn btn-primary">Dar de alta</button></div>
        </form>
      )}
      <div className="table-wrap" style={{ marginTop: 10 }}>
        <table className="data">
          <thead><tr><th>Proveedor</th><th>CIF</th><th>IBAN</th><th>Categoría</th><th>Pago</th><th style={{ textAlign: "right" }}>Pendiente</th></tr></thead>
          <tbody>{sups.map((s) => (
            <tr key={s.id}><td>{s.name}{s.recurring && <span className="badge" style={{ marginLeft: 6 }}>mensual</span>}{!s.active && <span className="badge badge-red" style={{ marginLeft: 6 }}>inactivo</span>}</td>
              <td className="mono">{s.tax_id}</td><td className="mono">{s.iban_masked ?? <span className="badge badge-yellow">sin IBAN</span>}</td>
              <td>{s.category_label}<div className="small muted">{ACTS[s.activity]}{s.branch ? ` · ${s.branch}` : ""}</div></td>
              <td>{s.payment_terms_days != null ? `${s.payment_terms_days} días` : "—"}</td><td style={{ textAlign: "right" }}>{fmtMoney(s.pending_cents)}</td></tr>
          ))}</tbody>
        </table>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ tesorería y remesas
interface Treasury { accounts: { id: string; name: string; bank: string; iban_last4: string; currency: string; has_iban: boolean; balance_cents: number | null; as_of: string | null; fiable: boolean; movimientos_sin_conciliar?: number }[]; bank_total_cents: number; cash_total_cents: number; payables: Record<string, number>; payables_total_cents: number; available_after_30_cents: number; note: string; can_propose: boolean; can_approve: boolean; can_manage_accounts: boolean }
interface Batch { id: string; code: string; account: string; account_has_iban: boolean; execution_date: string; total_cents: number; currency: string; status: string; proposed_by: string; note: string | null; closed_reason: string | null; items: { invoice_id: string; number: string; supplier: string; amount_cents: number; due_date: string | null; status: string }[]; paid: number; signatures: { by: string; decision: string; note: string | null; at: string }[]; signatures_needed: number; can_sign?: boolean; can_download?: boolean; can_mark_sent?: boolean; can_cancel?: boolean; sepa_sha256: string | null; sent_by: string | null }

export function TreasuryPanel({ orgId }: { orgId: string }) {
  const [t, setT] = useState<Treasury | null>(null);
  const [batches, setBatches] = useState<Batch[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const load = useCallback(() => {
    api<Treasury>(`/accounting/treasury?organization_id=${orgId}`).then(setT).catch((e) => setErr(errMsg(e)));
    api<Batch[]>(`/accounting/batches?organization_id=${orgId}`).then(setBatches).catch(() => setBatches([]));
  }, [orgId]);
  useEffect(() => { load(); }, [load]);
  if (!t) return err ? <div className="notice notice-danger">{err}</div> : <p className="muted">Cargando…</p>;
  const P = t.payables;
  return (
    <div className="stack">
      {msg && <div className="notice notice-ok" role="status">{msg}</div>}
      <div className="card">
        <h2>Saldos</h2>
        <div className="table-wrap"><table className="data">
          <thead><tr><th>Cuenta</th><th style={{ textAlign: "right" }}>Saldo</th><th>Según extracto del</th><th>IBAN para remesas</th></tr></thead>
          <tbody>
            {t.accounts.map((a) => (
              <tr key={a.id}><td>{a.name}<div className="small muted">{a.bank} · …{a.iban_last4}</div></td>
                <td style={{ textAlign: "right" }}><strong>{a.balance_cents == null ? "—" : fmtMoney(a.balance_cents, a.currency)}</strong></td>
                <td>{a.as_of ? fmtDate(a.as_of) : <span className="small muted">sin extracto</span>}{a.as_of && !a.fiable && <div><span className="badge badge-red">extracto con errores</span></div>}{!!a.movimientos_sin_conciliar && <div className="small muted">{a.movimientos_sin_conciliar} sin conciliar</div>}</td>
                <td>{a.has_iban ? <span className="badge badge-green">informado</span> : t.can_manage_accounts ? <IbanForm accId={a.id} last4={a.iban_last4} onDone={() => { setMsg("IBAN guardado (cifrado)."); load(); }} /> : <span className="badge badge-yellow">falta</span>}</td></tr>
            ))}
            <tr><td><strong>Cajas de las oficinas</strong></td><td style={{ textAlign: "right" }}><strong>{fmtMoney(t.cash_total_cents)}</strong></td><td colSpan={2} className="small muted">suma de movimientos de caja</td></tr>
          </tbody>
        </table></div>
      </div>
      <div className="card" aria-label="Previsión de pagos">
        <h2>Previsión de pagos a proveedores</h2>
        <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))" }}>
          {([["Vencido", P.vencido, true], ["Próximos 7 días", P["7"]], ["8–30 días", P["30"]], ["31–60 días", P["60"]], ["61–90 días", P["90"]], ["Sin vencimiento", P.sin_fecha]] as [string, number, boolean?][]).map(([l, v, red]) => (
            <div key={l} className="card" style={{ padding: 12 }}><div className="stat" style={{ fontSize: "1.3rem", color: red && v ? "var(--danger)" : undefined }}>{fmtMoney(v)}</div><div className="stat-label">{l}</div></div>
          ))}
        </div>
        <p className="small" style={{ marginBottom: 0 }}>Bancos + cajas − pagos a 30 días: <strong>{fmtMoney(t.available_after_30_cents)}</strong>. <span className="muted">{t.note}</span></p>
      </div>
      {t.can_propose && <NewBatch orgId={orgId} accounts={t.accounts} onDone={(m) => { setMsg(m); load(); }} />}
      <div className="card">
        <h2>Remesas</h2>
        <p className="small muted" style={{ marginTop: 0 }}>Cada remesa necesita dos firmas de personas distintas de quien la propone. El sistema genera el fichero SEPA; una persona lo sube a la banca electrónica. El pago se da por hecho cuando el cargo aparece en el extracto y se concilia.</p>
        {batches?.length === 0 && <p className="muted">Sin remesas.</p>}
        {batches?.map((b) => <BatchCard key={b.id} b={b} onDone={(m) => { setMsg(m); load(); }} />)}
      </div>
    </div>
  );
}

function IbanForm({ accId, last4, onDone }: { accId: string; last4: string; onDone: () => void }) {
  const [iban, setIban] = useState("");
  const [err, setErr] = useState<string | null>(null);
  async function save() {
    setErr(null);
    try { await api(`/accounting/accounts/${accId}/iban`, { method: "POST", body: JSON.stringify({ iban, reason: "Alta del IBAN para remesas" }) }); onDone(); }
    catch (e) { setErr(errMsg(e)); }
  }
  return <div className="row" style={{ gap: 4 }}><input aria-label={`IBAN completo de la cuenta …${last4}`} placeholder={`IBAN que termina en ${last4}`} value={iban} onChange={(e) => setIban(e.target.value)} style={{ width: 230 }} /><button className="btn btn-sm" onClick={save}>Guardar</button>{err && <span className="error-text small">{err}</span>}</div>;
}

function NewBatch({ orgId, accounts, onDone }: { orgId: string; accounts: Treasury["accounts"]; onDone: (m: string) => void }) {
  const [invs, setInvs] = useState<Invoice[] | null>(null);
  const [pick, setPick] = useState<Record<string, boolean>>({});
  const [acc, setAcc] = useState(accounts[0]?.id ?? "");
  const [day, setDay] = useState(madridDay(new Date()));
  const [err, setErr] = useState<string | null>(null);
  const load = useCallback(() => api<Invoice[]>(`/accounting/invoices?organization_id=${orgId}&status=validada`).then((r) => setInvs(r.filter((x) => !x.batch))).catch(() => setInvs([])), [orgId]);
  useEffect(() => { load(); }, [load]);
  const chosen = useMemo(() => (invs ?? []).filter((x) => pick[x.id]), [invs, pick]);
  async function propose() {
    setErr(null);
    try {
      const b = await api<Batch>("/accounting/batches", { method: "POST", body: JSON.stringify({ organization_id: orgId, account_id: acc, execution_date: day, invoice_ids: chosen.map((x) => x.id) }) });
      setPick({}); load(); onDone(`Remesa ${b.code} propuesta por ${fmtMoney(b.total_cents, b.currency)}: pendiente de dos firmas.`);
    } catch (e) { setErr(errMsg(e)); }
  }
  return (
    <div className="card stack" style={{ gap: 8 }} aria-label="Nueva remesa">
      <h2 style={{ margin: 0 }}>Proponer remesa de pagos</h2>
      {invs?.length === 0 && <p className="muted small">No hay facturas validadas pendientes de programar.</p>}
      {invs?.map((x) => (
        <label key={x.id} className="row small" style={{ gap: 6 }}>
          <input type="checkbox" style={{ width: "auto" }} checked={!!pick[x.id]} onChange={(e) => setPick({ ...pick, [x.id]: e.target.checked })} />
          <span>{x.supplier} · <span className="mono">{x.number}</span> · vence {x.due_date ? fmtDate(x.due_date) : "—"}</span>
          <strong>{fmtMoney(x.total_cents, x.currency)}</strong>{x.overdue && <span className="badge badge-red">vencida</span>}
        </label>
      ))}
      {!!invs?.length && (
        <div className="row">
          <select aria-label="Cuenta de cargo" value={acc} onChange={(e) => setAcc(e.target.value)} style={{ width: "auto" }}>{accounts.map((a) => <option key={a.id} value={a.id}>{a.name} (…{a.iban_last4}){a.has_iban ? "" : " · sin IBAN"}</option>)}</select>
          <input type="date" aria-label="Fecha de ejecución" value={day} onChange={(e) => setDay(e.target.value)} style={{ width: "auto" }} />
          <span>Total: <strong>{fmtMoney(chosen.reduce((s, x) => s + x.total_cents, 0))}</strong></span>
          <button className="btn btn-primary btn-sm" disabled={!chosen.length} onClick={propose}>Proponer remesa</button>
          {err && <span className="error-text small" role="alert">{err}</span>}
        </div>
      )}
    </div>
  );
}

function BatchCard({ b, onDone }: { b: Batch; onDone: (m: string) => void }) {
  const [note, setNote] = useState("");
  const [err, setErr] = useState<string | null>(null);
  async function act(path: string, body: object, ok: string) {
    setErr(null);
    try { await api(`/accounting/batches/${b.id}/${path}`, { method: "POST", body: JSON.stringify(body) }); onDone(ok); }
    catch (e) { setErr(errMsg(e)); }
  }
  return (
    <div className="notice notice-info" style={{ marginBottom: 10 }} aria-label={`Remesa ${b.code}`}>
      <div className="row"><strong className="mono">{b.code}</strong><span className={`badge ${BATCH_ST[b.status][1]}`}>{BATCH_ST[b.status][0]}</span>
        <span>{fmtMoney(b.total_cents, b.currency)} · {b.account} · ejecución {fmtDate(b.execution_date)}</span><span className="spacer" />
        <span className="small">Firmas: {b.signatures.filter((s) => s.decision === "autoriza").length}/2{b.status !== "propuesta" ? "" : ` · faltan ${b.signatures_needed}`}</span>
        {b.status === "enviada" && <span className="small">· pagadas {b.paid}/{b.items.length}</span>}</div>
      <div className="small">{b.items.map((i) => `${i.supplier} ${i.number} (${fmtMoney(i.amount_cents, b.currency)})`).join(" · ")}</div>
      <div className="small muted">Propuesta por {b.proposed_by}{b.signatures.map((s) => ` · ${s.decision === "autoriza" ? "autorizó" : "no autorizó"} ${s.by} (${fmtDateTime(s.at)})${s.note ? `: «${s.note}»` : ""}`).join("")}{b.closed_reason ? ` · ${b.closed_reason}` : ""}</div>
      {err && <div className="error-text small" role="alert">{err}</div>}
      <div className="row" style={{ marginTop: 6 }}>
        {b.can_sign && <><input aria-label={`Nota de firma ${b.code}`} placeholder="Nota (obligatoria si no autoriza)" value={note} onChange={(e) => setNote(e.target.value)} style={{ maxWidth: 260 }} />
          <button className="btn btn-sm btn-primary" onClick={() => act("sign", { approve: true, note: note || null }, `Ha firmado la remesa ${b.code}.`)}>Autorizar</button>
          <button className="btn btn-sm" onClick={() => act("sign", { approve: false, note }, `Remesa ${b.code} no autorizada.`)}>No autorizar</button></>}
        {b.can_download && (b.account_has_iban ? <a className="btn btn-sm" href={`/api/v1/accounting/batches/${b.id}/sepa.xml`}>Descargar fichero SEPA</a> : <span className="badge badge-yellow">Falta el IBAN de la cuenta para el fichero</span>)}
        {b.can_mark_sent && <button className="btn btn-sm" onClick={() => act("sent", {}, `Remesa ${b.code} marcada como subida al banco.`)}>Ya la he subido al banco</button>}
        {b.can_cancel && <button className="btn btn-sm" onClick={() => { const r = note || ""; if (r.length < 5) { setErr("Escriba el motivo en la nota para anularla."); return; } act("cancel", { reason: r }, `Remesa ${b.code} anulada.`); }}>Anular</button>}
        {b.can_cancel && !b.can_sign && <input aria-label={`Motivo de anulación ${b.code}`} placeholder="Motivo para anular" value={note} onChange={(e) => setNote(e.target.value)} style={{ maxWidth: 220 }} />}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ cuadro de mando y cierre del mes
type Bucket = Record<string, number | null>;
interface Figures { month: string; currency: string; total: Bucket; by_activity: Record<string, Bucket>; by_branch: Record<string, Bucket>; iva_soportado_dato_cents: number; treasury: { accounts: { name: string; iban_last4: string; balance_cents: number | null; as_of: string | null }[]; cash_cents: number; bank_cents: number }; pending: Record<string, number | string[]>; reliability: { indicators: Record<string, number | null>; level: string }; notes: string[]; previous?: { month: string; total: Bucket }; deviations?: Record<string, number | null>; personal_agrupado?: boolean }
interface Close { id: string; month: string; revision: number; status: string; figures: Figures; figures_sha256: string; prepared_by: string; prepared_at: string; reviewed_by: string | null; approved_by: string | null; approved_at: string | null; note: string | null; can_review: boolean; can_approve: boolean }
const LINES: [string, string][] = [["ingresos_devengados", "Ingresos devengados"], ["cobros", "Cobros"], ["gastos_proveedores", "Gastos de proveedores (base)"], ["gastos_empleados", "Gastos de empleados (sin IVA)"], ["coste_personal", "Coste de personal"], ["pagos", "Pagos a proveedores"], ["resultado", "Resultado provisional"]];
const PEND: Record<string, string> = { movimientos_sin_conciliar: "Movimientos del banco sin conciliar", facturas_sin_validar: "Facturas sin validar", cobros_sin_confirmar: "Cobros sin confirmar", cierres_caja_sin_validar: "Cierres de caja sin validar", nominas_sin_confirmar: "Nóminas sin confirmar", facturas_vencidas_sin_pagar: "Facturas vencidas sin pagar" };
const IND: Record<string, string> = { movimientos_conciliados_pct: "Banco conciliado", cobros_confirmados_pct: "Cobros confirmados", facturas_validadas_pct: "Facturas validadas", nominas_confirmadas_pct: "Nóminas confirmadas", cierres_caja_validados_pct: "Cierres de caja validados" };
const CLOSE_ST: Record<string, [string, string]> = { borrador: ["Borrador", "badge-yellow"], revisado: ["Revisado por Contabilidad", "badge-blue"], aprobado: ["Aprobado por Dirección", "badge-green"], sustituido: ["Sustituido", ""] };

export function ClosePanel({ orgId, canPrepare }: { orgId: string; canPrepare: boolean }) {
  const prevMonth = (() => { const d = new Date(); d.setDate(1); d.setMonth(d.getMonth() - 1); return madridDay(d).slice(0, 7); })();
  const [month, setMonth] = useState(prevMonth);
  const [fig, setFig] = useState<Figures | null>(null);
  const [closes, setCloses] = useState<Close[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const load = useCallback(() => {
    setFig(null);
    api<Figures>(`/accounting/dashboard?organization_id=${orgId}&month=${month}`).then(setFig).catch((e) => setErr(errMsg(e)));
    api<Close[]>(`/accounting/closes?organization_id=${orgId}`).then(setCloses).catch(() => setCloses([]));
  }, [orgId, month]);
  useEffect(() => { load(); }, [load]);
  const monthCloses = (closes ?? []).filter((c) => c.month === month);
  const current = monthCloses.find((c) => c.status !== "sustituido");
  async function prepare() {
    setErr(null);
    try { const c = await api<Close>("/accounting/closes", { method: "POST", body: JSON.stringify({ organization_id: orgId, month }) }); setMsg(`Cierre de ${month} preparado (revisión ${c.revision}).`); load(); }
    catch (e) { setErr(errMsg(e)); }
  }
  return (
    <div className="stack">
      <div className="row">
        <input type="month" aria-label="Mes del cierre" value={month} onChange={(e) => setMonth(e.target.value)} style={{ width: "auto" }} />
        {canPrepare && current?.status !== "aprobado" && <button className="btn btn-primary btn-sm" onClick={prepare}>{current ? "Recalcular (nueva revisión)" : `Preparar el cierre de ${month}`}</button>}
        <span className="small muted">El día 5 de cada mes el agente propone preparar el cierre del mes anterior.</span>
      </div>
      {msg && <div className="notice notice-ok" role="status">{msg}</div>}
      {err && <div className="notice notice-danger" role="alert">{err}</div>}
      {current && <CloseCard c={current} onDone={(m) => { setMsg(m); load(); }} />}
      {fig ? <Dashboard f={current ? current.figures : fig} frozen={!!current} /> : <p className="muted">Calculando…</p>}
      <div className="notice notice-info"><strong>Propuesta de asientos: no disponible aún</strong>Se activará cuando la gestoría facilite el plan de cuentas (T-40). Mientras tanto, el cierre se exporta en CSV.</div>
      {!!monthCloses.length && (
        <div className="card"><h2>Historial de {month}</h2>
          {monthCloses.map((c) => <div key={c.id} className="small">Revisión {c.revision} · <span className={`badge ${CLOSE_ST[c.status][1]}`}>{CLOSE_ST[c.status][0]}</span> · preparó {c.prepared_by} el {fmtDateTime(c.prepared_at)} · huella <span className="mono">{c.figures_sha256.slice(0, 12)}</span></div>)}
        </div>
      )}
    </div>
  );
}

function CloseCard({ c, onDone }: { c: Close; onDone: (m: string) => void }) {
  const [note, setNote] = useState("");
  const [err, setErr] = useState<string | null>(null);
  async function act(path: string, ok: string) {
    setErr(null);
    try { await api(`/accounting/closes/${c.id}/${path}`, { method: "POST", body: JSON.stringify({ note: note || null }) }); onDone(ok); }
    catch (e) { setErr(errMsg(e)); }
  }
  return (
    <div className={`notice ${c.status === "aprobado" ? "notice-ok" : "notice-warn"}`} aria-label={`Cierre ${c.month}`}>
      <div className="row"><strong>Cierre provisional {c.month} · revisión {c.revision}</strong><span className={`badge ${CLOSE_ST[c.status][1]}`}>{CLOSE_ST[c.status][0]}</span><span className="spacer" />
        <a className="btn btn-sm" href={`/api/v1/accounting/closes/${c.id}/export.csv`}>Exportar CSV</a></div>
      <div className="small">Preparó {c.prepared_by}{c.reviewed_by ? ` · revisó ${c.reviewed_by}` : ""}{c.approved_by ? ` · aprobó ${c.approved_by} el ${fmtDateTime(c.approved_at!)}` : ""} · cifras congeladas (huella {c.figures_sha256.slice(0, 12)}){c.note ? ` · ${c.note}` : ""}</div>
      {(c.can_review || c.can_approve) && (
        <div className="row" style={{ marginTop: 6 }}>
          <input aria-label="Nota del cierre" placeholder={c.can_review ? "Nota (obligatoria si hay pendientes)" : "Nota (opcional)"} value={note} onChange={(e) => setNote(e.target.value)} style={{ flex: 1, minWidth: 240 }} />
          {c.can_review && <button className="btn btn-sm btn-primary" onClick={() => act("review", "Cierre revisado: pendiente de aprobación de Dirección.")}>Dar por revisado</button>}
          {c.can_approve && <button className="btn btn-sm btn-primary" onClick={() => act("approve", "Cierre aprobado y congelado.")}>Aprobar cierre</button>}
        </div>
      )}
      {err && <div className="error-text small" role="alert">{err}</div>}
    </div>
  );
}

function Dashboard({ f, frozen }: { f: Figures; frozen: boolean }) {
  const acts = ["laboral", "extranjeria", "compartida", "sin_asignar"];
  const cell = (v: number | null | undefined) => (v === null || v === undefined ? <span className="muted" title="Agrupado: menos de 3 personas">agrupado</span> : fmtMoney(v, f.currency));
  const lvl = f.reliability.level;
  return (
    <div className="stack" aria-label="Cuadro de mando">
      <div className="card">
        <div className="row"><h2 style={{ margin: 0 }}>Resultado de {f.month}{frozen ? " (cifras del cierre)" : " (en vivo)"}</h2><span className="spacer" />
          <span className={`badge ${lvl === "alta" ? "badge-green" : lvl === "media" ? "badge-yellow" : "badge-red"}`}>Fiabilidad {lvl.replace("_", " ")}</span></div>
        <div className="table-wrap" style={{ marginTop: 10 }}>
          <table className="data">
            <thead><tr><th>Concepto</th>{acts.map((a) => <th key={a} style={{ textAlign: "right" }}>{ACTS[a]}</th>)}<th style={{ textAlign: "right" }}>Total</th><th style={{ textAlign: "right" }}>{f.previous ? f.previous.month : "Anterior"}</th></tr></thead>
            <tbody>{LINES.map(([k, l]) => {
              const dev = f.deviations?.[k];
              return (
                <tr key={k} style={k === "resultado" ? { fontWeight: 700 } : undefined}>
                  <td>{l}</td>{acts.map((a) => <td key={a} style={{ textAlign: "right" }}>{cell(f.by_activity[a]?.[k])}</td>)}
                  <td style={{ textAlign: "right" }}><strong>{cell(f.total[k])}</strong></td>
                  <td style={{ textAlign: "right" }}>{cell(f.previous?.total[k])}{dev !== undefined && <div><span className="badge badge-yellow">{dev === null ? "nuevo" : `${dev > 0 ? "+" : ""}${dev} %`}</span></div>}</td>
                </tr>
              );
            })}</tbody>
          </table>
        </div>
        <p className="small muted" style={{ marginBottom: 0 }}>IVA soportado (dato de las facturas): {fmtMoney(f.iva_soportado_dato_cents, f.currency)}.{f.personal_agrupado ? " El coste de personal de grupos de menos de 3 personas se muestra agrupado (protección de salarios)." : ""}</p>
      </div>
      <div className="grid grid-2">
        <div className="card">
          <h2>Por oficina</h2>
          <div className="table-wrap"><table className="data">
            <thead><tr><th>Oficina</th><th style={{ textAlign: "right" }}>Ingresos</th><th style={{ textAlign: "right" }}>Gastos</th><th style={{ textAlign: "right" }}>Personal</th><th style={{ textAlign: "right" }}>Resultado</th></tr></thead>
            <tbody>{Object.entries(f.by_branch).map(([b, v]) => (
              <tr key={b}><td>{b}</td><td style={{ textAlign: "right" }}>{cell(v.ingresos_devengados)}</td><td style={{ textAlign: "right" }}>{cell((v.gastos_proveedores ?? 0) + (v.gastos_empleados ?? 0))}</td><td style={{ textAlign: "right" }}>{cell(v.coste_personal)}</td><td style={{ textAlign: "right" }}><strong>{cell(v.resultado)}</strong></td></tr>
            ))}</tbody>
          </table></div>
        </div>
        <div className="card">
          <h2>Pendientes y fiabilidad</h2>
          {Object.entries(PEND).map(([k, l]) => { const v = f.pending[k] as number; return <div key={k} className="row small"><span>{l}</span><span className="spacer" />{v ? <span className="badge badge-red">{v}</span> : <span className="badge badge-green">0</span>}</div>; })}
          {(f.pending.accounts_sin_extracto as string[]).length > 0 && <div className="small" style={{ marginTop: 6 }}><span className="badge badge-yellow">Sin extracto a fin de mes</span> {(f.pending.accounts_sin_extracto as string[]).join(", ")}</div>}
          <hr />
          {Object.entries(IND).map(([k, l]) => <div key={k} className="row small"><span>{l}</span><span className="spacer" /><span>{f.reliability.indicators[k] == null ? "—" : `${f.reliability.indicators[k]} %`}</span></div>)}
          <hr />
          <div className="small"><strong>Tesorería a fin de mes:</strong> bancos {fmtMoney(f.treasury.bank_cents, f.currency)} · cajas {fmtMoney(f.treasury.cash_cents, f.currency)}</div>
        </div>
      </div>
      <ul className="small muted" style={{ margin: 0 }}>{f.notes.map((n) => <li key={n}>{n}</li>)}</ul>
    </div>
  );
}

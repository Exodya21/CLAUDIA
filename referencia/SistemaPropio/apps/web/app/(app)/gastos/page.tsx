"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { StatusBadge } from "@/components/economy";
import { CSRF_HEADER, api, ApiError, parseError } from "@/lib/api";
import { ESTADOS_GASTO, FORMAS_PAGO_GASTO, fmtDate, fmtMoney, label } from "@/lib/format";
import type { ExpenseCatalog, ExpenseRow } from "@/lib/api";

type Tab = "mios" | "revision" | "tarjetas" | "resumen";

export default function Gastos() {
  const [cat, setCat] = useState<ExpenseCatalog | null>(null);
  const [tab, setTab] = useState<Tab>("mios");
  useEffect(() => { api<ExpenseCatalog>("/expenses/catalog").then(setCat).catch(() => undefined); }, []);
  if (!cat) return <p className="muted">Cargando…</p>;
  const tabs: [Tab, string, boolean][] = [
    ["mios", "Mis gastos", true], ["revision", "Revisión", cat.can_review], ["tarjetas", "Tarjetas y extractos", cat.can_review],
    ["resumen", "Resumen mensual", cat.can_read_all || cat.can_review],
  ];
  return (
    <div className="stack">
      <div className="topline">
        <div>
          <h1>Gastos</h1>
          <p className="subtitle">Suba la foto o el PDF del ticket: el sistema propone los datos y usted los confirma. Contabilidad los revisa y concilia.</p>
        </div>
      </div>
      <div className="tabs" role="tablist">
        {tabs.filter((t) => t[2]).map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}>{l}</button>)}
      </div>
      {tab === "mios" && <Mine cat={cat} />}
      {tab === "revision" && <ExpenseList scope="all" status="enviado" empty="No hay gastos pendientes de revisión." />}
      {tab === "tarjetas" && <Cards cat={cat} />}
      {tab === "resumen" && <MonthSummary />}
    </div>
  );
}

function Mine({ cat }: { cat: ExpenseCatalog }) {
  const router = useRouter();
  const input = useRef<HTMLInputElement>(null);
  const [org, setOrg] = useState(cat.organizations[0]?.id ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dup, setDup] = useState<string | null>(null);
  async function upload(f: File) {
    setBusy(true); setError(null); setDup(null);
    const fd = new FormData();
    fd.append("file", f);
    if (org) fd.append("organization_id", org);
    const res = await fetch("/api/v1/expenses", { method: "POST", body: fd, headers: CSRF_HEADER, credentials: "same-origin" });
    const data = await res.json().catch(() => null);
    setBusy(false);
    if (input.current) input.current.value = "";
    if (!res.ok) {
      const err = parseError(res.status, data);
      setError(err.message);
      const d = err.body.details as { expense_id?: string } | null;
      if (d?.expense_id) setDup(d.expense_id);
      return;
    }
    router.push(`/gastos/${data.id}?nuevo=1`);
  }
  return (
    <div className="stack">
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Nuevo gasto</h2>
        {cat.organizations.length > 1 && (
          <label className="field" style={{ maxWidth: 380 }}>Entidad que paga el gasto
            <select value={org} onChange={(e) => setOrg(e.target.value)}>{cat.organizations.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}</select>
          </label>
        )}
        <div className="row" style={{ marginTop: 10 }}>
          <label className="btn btn-primary" style={{ cursor: busy ? "wait" : "pointer" }}>
            {busy ? "Leyendo el justificante…" : "Subir foto o PDF del ticket"}
            <input ref={input} type="file" accept="image/jpeg,image/png,application/pdf" capture="environment" hidden disabled={busy}
              aria-label="Justificante" onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
          </label>
          <span className="small muted">JPG, PNG o PDF · máx. 10 MB · {cat.ocr_available ? "lectura automática dentro del servidor" : "lectura automática no instalada: rellenará los datos a mano"}</span>
        </div>
        {error && <div className="notice notice-danger" style={{ marginTop: 10 }}>{error}{dup && <> <Link href={`/gastos/${dup}`}>Ver el gasto ya registrado</Link></>}</div>}
      </div>
      <ExpenseList scope="mine" empty="Todavía no ha registrado gastos." />
    </div>
  );
}

function ExpenseList({ scope, status, empty }: { scope: "mine" | "all"; status?: string; empty: string }) {
  const [rows, setRows] = useState<ExpenseRow[] | null>(null);
  const [st, setSt] = useState(status ?? "");
  useEffect(() => {
    const q = new URLSearchParams({ scope });
    if (st) q.set("status", st);
    api<ExpenseRow[]>(`/expenses?${q}`).then(setRows).catch(() => setRows([]));
  }, [scope, st]);
  return (
    <div className="card">
      <div className="row">
        <h2 style={{ margin: 0 }}>{scope === "mine" ? "Mis gastos" : "Gastos"}</h2><span className="spacer" />
        <select aria-label="Estado del gasto" style={{ width: 230 }} value={st} onChange={(e) => setSt(e.target.value)}>
          <option value="">Todos los estados</option>
          {Object.entries(ESTADOS_GASTO).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </div>
      <div className="table-wrap" style={{ marginTop: 10 }}>
        <table className="data">
          <thead><tr><th>Fecha</th>{scope === "all" && <th>Persona</th>}<th>Proveedor</th><th>Forma de pago</th><th style={{ textAlign: "right" }}>Importe</th><th>Estado</th></tr></thead>
          <tbody>
            {rows?.length === 0 && <tr><td colSpan={6} className="empty">{empty}</td></tr>}
            {rows?.map((e) => (
              <tr key={e.id}>
                <td>{e.expense_date ? fmtDate(e.expense_date) : "—"}</td>
                {scope === "all" && <td>{e.employee}<div className="small muted">{e.branch}</div></td>}
                <td><Link href={`/gastos/${e.id}`}>{e.supplier_name ?? "(sin proveedor)"}</Link></td>
                <td className="small">{e.payment_method ? label(FORMAS_PAGO_GASTO, e.payment_method) : "—"}</td>
                <td style={{ textAlign: "right" }}>{fmtMoney(e.amount_cents, e.currency)}</td>
                <td><StatusBadge map={ESTADOS_GASTO} s={e.status} />{e.status === "devuelto" && e.review_note && <div className="small muted">{e.review_note}</div>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

interface Card { id: string; label: string; last4: string; holder: string; active: boolean; organization_id: string }
interface Txn { id: string; date: string; description: string; amount_cents: number; card: string; holder: string; suggestions: { id: string; supplier_name: string | null; status: string; expense_date: string | null }[] }

function Cards({ cat }: { cat: ExpenseCatalog }) {
  const [cards, setCards] = useState<Card[]>([]);
  const [txns, setTxns] = useState<Txn[]>([]);
  const [holders, setHolders] = useState<{ id: string; full_name: string; organization_id: string }[]>([]);
  const [org, setOrg] = useState(cat.organizations[0]?.id ?? "");
  const [form, setForm] = useState({ holder_user_id: "", last4: "", label: "" });
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const load = useCallback(() => {
    api<Card[]>("/expenses/cards/all").then(setCards).catch(() => setCards([]));
    api<Txn[]>("/expenses/cards/transactions").then(setTxns).catch(() => setTxns([]));
  }, []);
  useEffect(() => { load(); api<typeof holders>("/expenses/cards/holders").then(setHolders).catch(() => undefined); }, [load]);
  async function addCard(e: React.FormEvent) {
    e.preventDefault(); setMsg(null);
    try { await api("/expenses/cards", { method: "POST", body: JSON.stringify({ ...form, organization_id: org }) }); setForm({ holder_user_id: "", last4: "", label: "" }); load(); setMsg({ ok: true, text: "Tarjeta registrada." }); }
    catch (err) { setMsg({ ok: false, text: err instanceof ApiError ? err.message : "Error" }); }
  }
  async function importCsv(f: File) {
    setMsg(null);
    const fd = new FormData();
    fd.append("file", f);
    fd.append("organization_id", org);
    const res = await fetch("/api/v1/expenses/cards/import", { method: "POST", body: fd, headers: CSRF_HEADER, credentials: "same-origin" });
    const data = await res.json().catch(() => null);
    if (!res.ok) { setMsg({ ok: false, text: parseError(res.status, data).message }); return; }
    setMsg({ ok: data.errors.length === 0, text: `Extracto importado: ${data.imported} movimientos nuevos, ${data.duplicates} ya estaban, ${data.with_suggestion} con justificante propuesto.` +
      (data.errors.length ? ` Líneas no leídas: ${data.errors.map((x: { linea: number; error: string }) => `${x.linea} (${x.error})`).join("; ")}` : "") });
    load();
  }
  async function match(expenseId: string, txnId: string) {
    setMsg(null);
    try { await api(`/expenses/${expenseId}/reconcile`, { method: "POST", body: JSON.stringify({ card_transaction_id: txnId }) }); load(); setMsg({ ok: true, text: "Gasto conciliado con el extracto." }); }
    catch (err) { setMsg({ ok: false, text: err instanceof ApiError ? err.message : "Error" }); }
  }
  return (
    <div className="stack">
      {msg && <div className={`notice ${msg.ok ? "notice-ok" : "notice-warn"}`}>{msg.text}</div>}
      {cat.organizations.length > 1 && (
        <label className="field" style={{ maxWidth: 380 }}>Entidad
          <select value={org} onChange={(e) => setOrg(e.target.value)}>{cat.organizations.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}</select>
        </label>
      )}
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Cargos de tarjeta sin conciliar</h2>
        <div className="row" style={{ marginBottom: 10 }}>
          <label className="btn btn-primary">Importar extracto (CSV)
            <input type="file" accept=".csv,text/csv" hidden aria-label="Extracto CSV" onChange={(e) => { if (e.target.files?.[0]) importCsv(e.target.files[0]); e.target.value = ""; }} />
          </label>
          <span className="small muted">Columnas: <span className="mono">fecha;concepto;importe;tarjeta</span> (4 últimos dígitos). Reimportar no duplica.</span>
        </div>
        <div className="table-wrap">
          <table className="data">
            <thead><tr><th>Fecha</th><th>Tarjeta</th><th>Concepto del banco</th><th style={{ textAlign: "right" }}>Importe</th><th>Justificante</th></tr></thead>
            <tbody>
              {txns.length === 0 && <tr><td colSpan={5} className="empty">No hay cargos pendientes.</td></tr>}
              {txns.map((t) => (
                <tr key={t.id}>
                  <td>{fmtDate(t.date)}</td><td className="small">{t.card}<div className="muted">{t.holder}</div></td><td>{t.description}</td>
                  <td style={{ textAlign: "right" }}>{fmtMoney(t.amount_cents)}</td>
                  <td>{t.suggestions.length === 0 ? <span className="badge badge-red">Sin justificante</span> : t.suggestions.map((s) => (
                    <div key={s.id} className="row small">
                      <Link href={`/gastos/${s.id}`}>{s.supplier_name ?? "gasto"} · {s.expense_date ? fmtDate(s.expense_date) : ""}</Link>
                      {s.status === "aprobado" ? <button className="btn btn-sm btn-primary" onClick={() => match(s.id, t.id)}>Conciliar</button>
                        : <span className="muted">(apruébelo antes)</span>}
                    </div>
                  ))}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Tarjetas de empresa</h2>
        <table className="data">
          <thead><tr><th>Tarjeta</th><th>Titular</th><th>Estado</th></tr></thead>
          <tbody>{cards.map((c) => <tr key={c.id}><td>{c.label} <span className="mono">··{c.last4}</span></td><td>{c.holder}</td><td>{c.active ? "Activa" : "Baja"}</td></tr>)}</tbody>
        </table>
        <form className="form-grid" style={{ marginTop: 12 }} onSubmit={addCard}>
          <label className="field">Titular
            <select value={form.holder_user_id} onChange={(e) => setForm({ ...form, holder_user_id: e.target.value })} required>
              <option value="">Elija…</option>
              {holders.filter((h) => h.organization_id === org).map((h) => <option key={h.id} value={h.id}>{h.full_name}</option>)}
            </select>
          </label>
          <label className="field">4 últimos dígitos <span className="hint">nunca el número completo</span>
            <input inputMode="numeric" pattern="\d{4}" maxLength={4} value={form.last4} onChange={(e) => setForm({ ...form, last4: e.target.value })} required />
          </label>
          <label className="field full">Nombre de la tarjeta<input value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })} minLength={3} required placeholder="p. ej. Visa empresa Laboral BCN" /></label>
          <div className="full"><button className="btn">Registrar tarjeta</button></div>
        </form>
      </div>
    </div>
  );
}

interface Group { total: number; iva: number; n: number }
interface MonthSum { month: string; total: Group; por_estado: Record<string, number>; grupos: Record<string, Record<string, Group>>; cargos_tarjeta_sin_justificante: number }

function MonthSummary() {
  const now = new Date();
  const [month, setMonth] = useState(`${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`);
  const [s, setS] = useState<MonthSum | null>(null);
  useEffect(() => { api<MonthSum>(`/expenses/summary/month?month=${month}`).then(setS).catch(() => setS(null)); }, [month]);
  const titles: Record<string, string> = { empleado: "Por persona", sede: "Por sede", concepto: "Por concepto", forma_pago: "Por forma de pago" };
  return (
    <div className="stack">
      <div className="card row">
        <label className="field">Mes<input type="month" value={month} onChange={(e) => setMonth(e.target.value)} /></label>
        <span className="spacer" />
        <a className="btn" href={`/api/v1/expenses/summary/month.csv?month=${month}`}>Descargar para Excel (CSV)</a>
      </div>
      {s && (
        <>
          <div className="grid grid-3">
            <div className="card stat"><div className="stat-label">Total del mes</div><strong>{fmtMoney(s.total.total)}</strong><div className="small muted">{s.total.n} gastos · IVA {fmtMoney(s.total.iva)}</div></div>
            <div className="card stat"><div className="stat-label">Pendientes de revisar</div><strong>{s.por_estado.enviado ?? 0}</strong><div className="small muted">devueltos: {s.por_estado.devuelto ?? 0}</div></div>
            <div className="card stat"><div className="stat-label">Cargos de tarjeta sin justificante</div><strong style={{ color: s.cargos_tarjeta_sin_justificante ? "var(--danger)" : undefined }}>{s.cargos_tarjeta_sin_justificante}</strong></div>
          </div>
          <div className="grid grid-2">
            {Object.entries(s.grupos).map(([g, rows]) => (
              <div key={g} className="card">
                <h3 style={{ marginTop: 0 }}>{titles[g]}</h3>
                <table className="data">
                  <tbody>
                    {Object.entries(rows).map(([k, v]) => <tr key={k}><td>{g === "forma_pago" ? label(FORMAS_PAGO_GASTO, k) : k}</td><td className="small muted">{v.n}</td><td style={{ textAlign: "right" }}>{fmtMoney(v.total)}</td></tr>)}
                    {Object.keys(rows).length === 0 && <tr><td className="empty">Sin gastos.</td></tr>}
                  </tbody>
                </table>
              </div>
            ))}
          </div>
          <p className="small muted">Incluye gastos enviados, devueltos, aprobados y conciliados con fecha de este mes. El IVA es el que figura en los justificantes; su tratamiento fiscal lo decide Contabilidad.</p>
        </>
      )}
    </div>
  );
}

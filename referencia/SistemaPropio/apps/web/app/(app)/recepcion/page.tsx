"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { MoneyInput } from "@/components/economy";
import { PendingList } from "@/components/proposals";
import { api, ApiError, fieldErrors } from "@/lib/api";
import { fmtDate, fmtDateTime, fmtMoney, fmtTime, label, MATERIAS, METODOS_COBRO, parseMoney } from "@/lib/format";

interface BranchInfo { id: string; name: string; organization_id: string; organization: string; currency: string; can_operate: boolean; can_charge: boolean; can_validate: boolean; can_balance: boolean }
interface Pay { id: string; kind: string | null; amount_cents: number; currency: string; method: string; received_at: string; reference: string | null; status: string; case_code: string | null; contact_name: string; registered_by: string; duplicate_reason: string | null; receipt: { number: string; url: string } | null }
interface Closing { id: string; day: string; expected_cents: number; counted_cents: number; difference_cents: number; notes: string | null; status: string; closed_by: string; closed_at: string; validated_by: string | null; validation_note: string | null; branch: string; can_decide?: boolean }
interface Day {
  branch: { id: string; name: string }; day: string; is_today: boolean; currency: string; payments: Pay[];
  totals: { cobros: number; importe_cents: number; por_forma: Record<string, number> };
  cash: { opening_cents: number; movements: { id: string; kind: string; amount_cents: number; concept: string; at: string; by: string }[]; in_cents: number; out_cents: number; balance_cents: number };
  closings: Closing[]; can_close: boolean; can_charge: boolean;
}

const KINDS: Record<string, string> = { consulta: "Consulta", provision: "Provisión de fondos", servicio: "Servicio", otro: "Otro" };
const CLOSE_ST: Record<string, [string, string]> = {
  pendiente_validacion: ["Pendiente de validar", "badge-yellow"], validado: ["Validado", "badge-green"], rechazado: ["Rechazado (volver a contar)", "badge-red"],
};
type Tab = "cobrar" | "caja" | "informe" | "pendientes";
const madridDay = (d: Date) => d.toLocaleDateString("sv-SE", { timeZone: "Europe/Madrid" });
const errMsg = (e: unknown) => (e instanceof ApiError ? e.message : "No se ha podido completar la operación.");

function Recepcion() {
  const params = useSearchParams();
  const [branches, setBranches] = useState<BranchInfo[] | null>(null);
  const [sel, setSel] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>(params.get("tab") === "pendientes" ? "pendientes" : "cobrar");
  const [pending, setPending] = useState<number | null>(null);
  const [tick, setTick] = useState(0);
  useEffect(() => { api<BranchInfo[]>("/reception/branches").then((b) => { setBranches(b); setSel((s) => s ?? b.find((x) => x.can_operate)?.id ?? b[0]?.id ?? null); }).catch(() => setBranches([])); }, []);
  const b = branches?.find((x) => x.id === sel) ?? null;
  if (branches && branches.length === 0) return <div className="notice notice-warn"><strong>Sin acceso</strong>Su perfil no tiene ninguna recepción ni caja a su cargo.</div>;
  return (
    <div className="stack">
      <div className="topline">
        <div>
          <h1>Recepción</h1>
          <p className="subtitle">Cobros de consultas, provisiones y servicios con su justificante (no es factura), caja del día con cierre validado por un responsable e informe por sede. Cada cobro se registra una sola vez.</p>
        </div>
        {branches && branches.length > 1 && (
          <select aria-label="Sede" value={sel ?? ""} onChange={(e) => setSel(e.target.value)} style={{ width: "auto" }}>
            {branches.map((x) => <option key={x.id} value={x.id}>{x.name}{x.can_operate ? "" : " (consulta)"}</option>)}
          </select>
        )}
      </div>
      <div className="tabs" role="tablist">
        {b?.can_charge && <button role="tab" aria-selected={tab === "cobrar"} onClick={() => setTab("cobrar")}>Cobrar</button>}
        <button role="tab" aria-selected={tab === "caja"} onClick={() => setTab("caja")}>Caja del día</button>
        <button role="tab" aria-selected={tab === "informe"} onClick={() => setTab("informe")}>Informe</button>
        <button role="tab" aria-selected={tab === "pendientes"} onClick={() => setTab("pendientes")}>Pendientes{pending ? ` (${pending})` : ""}</button>
      </div>
      {b && tab === "cobrar" && b.can_charge && <Charge b={b} onDone={() => setTick((t) => t + 1)} />}
      {b && (tab === "caja" || (tab === "cobrar" && !b.can_charge)) && <CashDay key={`${b.id}:${tick}`} b={b} />}
      {b && tab === "informe" && <Report b={b} all={branches ?? []} />}
      <div hidden={tab !== "pendientes"}>
        <PendingList params={{ agent: "recepcion" }} decided onCount={setPending}
          empty="No hay cierres por validar, cobros repetidos ni cajas sin cerrar." />
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ cobrar
interface ContactHit { id: string; display_name?: string; given_name?: string; family_names?: string; primary_branch: string | null; phones_masked: string[]; organization_id: string }
interface CaseRow { id: string; code: string; materia: string; status: string; pendiente_cents?: number; cargado_cents?: number; cobrado_cents?: number }

function Charge({ b, onDone }: { b: BranchInfo; onDone: () => void }) {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<ContactHit[] | null>(null);
  const [contact, setContact] = useState<{ id: string; name: string } | null>(null);
  const [cases, setCases] = useState<{ cases: CaseRow[]; show_balance: boolean } | null>(null);
  const [caseId, setCaseId] = useState<string>("");
  const [kind, setKind] = useState("consulta");
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState("efectivo");
  const [ref, setRef] = useState("");
  const [notes, setNotes] = useState("");
  const [dups, setDups] = useState<Pay[] | null>(null);
  const [dupReason, setDupReason] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [fe, setFe] = useState<Record<string, string>>({});
  const [done, setDone] = useState<Pay | null>(null);
  const [busy, setBusy] = useState(false);

  async function search(e: React.FormEvent) {
    e.preventDefault();
    const r = await api<{ items: ContactHit[] }>(`/contacts?q=${encodeURIComponent(q)}&page_size=10`).catch(() => ({ items: [] }));
    setHits(r.items.filter((x) => x.organization_id === b.organization_id));
  }
  async function pick(h: ContactHit) {
    const name = h.display_name ?? `${h.given_name} ${h.family_names}`;
    setContact({ id: h.id, name }); setHits(null); setCaseId(""); setKind("consulta");
    setCases(await api<{ cases: CaseRow[]; show_balance: boolean }>(`/reception/contacts/${h.id}/cases`).catch(() => ({ cases: [], show_balance: false })));
  }
  function reset() { setContact(null); setCases(null); setCaseId(""); setAmount(""); setRef(""); setNotes(""); setDups(null); setDupReason(""); setErr(null); setFe({}); setQ(""); }
  async function submit(e: React.FormEvent) {
    e.preventDefault(); setErr(null); setFe({});
    const cents = parseMoney(amount);
    if (!cents) { setFe({ amount_cents: "Importe no válido" }); return; }
    setBusy(true);
    try {
      const p = await api<Pay>("/reception/payments", { method: "POST", body: JSON.stringify({
        branch_id: b.id, contact_id: contact!.id, case_id: caseId || null, kind, amount_cents: cents, method,
        reference: ref || null, notes: notes || null, duplicate_reason: dups ? dupReason : null }) });
      setDone(p); reset(); onDone();
    } catch (ex) {
      if (ex instanceof ApiError && ex.body.code === "posible_duplicado") setDups(ex.body.details as Pay[]);
      else { setErr(errMsg(ex)); setFe(fieldErrors(ex)); }
    } finally { setBusy(false); }
  }
  const chosen = cases?.cases.find((c) => c.id === caseId);
  return (
    <div className="stack">
      {done && (
        <div className="notice notice-ok" role="status">
          <strong>Cobro registrado · justificante {done.receipt?.number}</strong>
          {fmtMoney(done.amount_cents, done.currency)} · {label(METODOS_COBRO, done.method)} · {done.contact_name}{done.case_code ? ` · ${done.case_code}` : " · consulta"}.
          <div className="row" style={{ marginTop: 8 }}>
            {done.receipt && <a className="btn btn-sm btn-primary" href={`/api/v1${done.receipt.url}`} target="_blank" rel="noreferrer">Ver e imprimir el justificante</a>}
            <button className="btn btn-sm" onClick={() => setDone(null)}>Cobrar otro</button>
          </div>
        </div>
      )}
      {!contact && !done && (
        <div className="card stack" style={{ gap: 10 }}>
          <form className="row" onSubmit={search}>
            <input className="search" aria-label="Buscar cliente" placeholder="Nombre, teléfono o documento del cliente" value={q} onChange={(e) => setQ(e.target.value)} required minLength={2} />
            <button className="btn">Buscar</button>
            <Link className="btn btn-sm" href="/clientes/nuevo">Dar de alta un cliente</Link>
          </form>
          {hits?.length === 0 && <p className="muted small">No hay coincidencias en esta entidad.</p>}
          {hits?.map((h) => (
            <button key={h.id} className="inbox-item" onClick={() => pick(h)}>
              <strong>{h.display_name ?? `${h.given_name} ${h.family_names}`}</strong>
              <span className="small muted">{h.primary_branch ?? "—"}{h.phones_masked?.length ? ` · ${h.phones_masked[0]}` : ""}</span>
            </button>
          ))}
        </div>
      )}
      {contact && (
        <form className="card stack" style={{ gap: 12 }} onSubmit={submit} aria-label="Registrar cobro">
          <div className="row"><strong>{contact.name}</strong><span className="spacer" /><button type="button" className="btn btn-sm" onClick={reset}>Cambiar de cliente</button></div>
          <fieldset className="stack" style={{ gap: 6, border: "none", padding: 0, margin: 0 }}>
            <legend className="small" style={{ fontWeight: 600 }}>¿A qué corresponde?</legend>
            <label className="row small"><input type="radio" name="case" checked={caseId === ""} onChange={() => { setCaseId(""); setKind("consulta"); }} /> Consulta (sin expediente)</label>
            {cases?.cases.map((c) => (
              <label key={c.id} className="row small">
                <input type="radio" name="case" checked={caseId === c.id} onChange={() => { setCaseId(c.id); if (kind === "consulta") setKind("provision"); }} />
                <span className="mono">{c.code}</span> {label(MATERIAS, c.materia)} · {c.status}
                {cases.show_balance && c.pendiente_cents !== undefined && <span className={`badge ${c.pendiente_cents > 0 ? "badge-yellow" : "badge-green"}`}>{c.pendiente_cents > 0 ? `Pendiente ${fmtMoney(c.pendiente_cents, b.currency)}` : "Sin pendiente"}</span>}
              </label>
            ))}
          </fieldset>
          <div className="form-grid">
            <label className="field">Concepto
              <select value={kind} onChange={(e) => setKind(e.target.value)}>
                {Object.entries(KINDS).map(([k, v]) => <option key={k} value={k} disabled={!caseId && k !== "consulta"}>{v}</option>)}
              </select>
            </label>
            <MoneyInput label="Importe recibido" value={amount} onChange={setAmount} error={fe.amount_cents} />
            <label className="field">Forma de pago
              <select value={method} onChange={(e) => setMethod(e.target.value)}>
                {["efectivo", "tarjeta", "bizum", "transferencia"].map((m) => <option key={m} value={m}>{label(METODOS_COBRO, m)}</option>)}
              </select>
            </label>
            {(method === "transferencia" || method === "bizum") && (
              <label className="field">Referencia *<input value={ref} onChange={(e) => setRef(e.target.value)} required />{fe.reference && <span className="error-text">{fe.reference}</span>}</label>
            )}
            <label className="field full">Notas (opcional)<input value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={500} /></label>
          </div>
          {chosen && chosen.pendiente_cents !== undefined && parseMoney(amount) !== null && (parseMoney(amount) ?? 0) > chosen.pendiente_cents && chosen.pendiente_cents >= 0 && (
            <div className="notice notice-warn small">El importe supera lo pendiente de este expediente ({fmtMoney(chosen.pendiente_cents, b.currency)}). Compruébelo con el responsable antes de cobrar.</div>
          )}
          {dups && (
            <div className="notice notice-warn" role="alert">
              <strong>Parece que este cobro ya está registrado</strong>
              {dups.map((d) => <div key={d.id} className="small">{fmtDateTime(d.received_at)} · {fmtMoney(d.amount_cents, d.currency)} · {label(METODOS_COBRO, d.method)} · {d.case_code ?? "consulta"} · {d.registered_by}{d.receipt ? ` · ${d.receipt.number}` : ""}</div>)}
              <label className="field" style={{ marginTop: 8 }}>Si es un cobro distinto, explique por qué (Contabilidad lo revisará)
                <input value={dupReason} onChange={(e) => setDupReason(e.target.value)} minLength={10} required />
              </label>
            </div>
          )}
          {err && <div className="notice notice-danger" role="alert">{err}</div>}
          <div className="row">
            <button className="btn btn-primary" disabled={busy}>{dups ? "Registrar de todos modos" : "Registrar cobro y emitir justificante"}</button>
            <span className="small muted">El justificante no es una factura: la factura sale del programa homologado.</span>
          </div>
        </form>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ caja del día
function CashDay({ b }: { b: BranchInfo }) {
  const [day, setDay] = useState<string>("");
  const [d, setD] = useState<Day | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [counted, setCounted] = useState("");
  const [note, setNote] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const load = useCallback(() => api<Day>(`/reception/day?branch_id=${b.id}${day ? `&day=${day}` : ""}`).then((r) => { setD(r); setErr(null); }).catch((e) => setErr(errMsg(e))), [b.id, day]);
  useEffect(() => { load(); }, [load]);
  const countedCents = parseMoney(counted);
  const diff = useMemo(() => (countedCents !== null && d ? countedCents - d.cash.balance_cents : null), [countedCents, d]);
  async function close(e: React.FormEvent) {
    e.preventDefault(); setErr(null);
    try {
      await api(`/reception/cash/${b.id}/close`, { method: "POST", body: JSON.stringify({ counted_cents: countedCents, notes: note || null }) });
      setMsg("Caja cerrada. Queda pendiente de que un responsable la valide."); setCounted(""); setNote(""); load();
    } catch (ex) { setErr(errMsg(ex)); }
  }
  if (!d) return err ? <div className="notice notice-danger">{err}</div> : <p className="muted">Cargando…</p>;
  return (
    <div className="stack">
      <div className="row">
        <input type="date" aria-label="Día" value={day || d.day} onChange={(e) => setDay(e.target.value)} style={{ width: "auto" }} />
        {!d.is_today && <button className="btn btn-sm" onClick={() => setDay("")}>Hoy</button>}
        <strong>{b.name}</strong><span className="muted small">{fmtDate(d.day)}</span>
      </div>
      {msg && <div className="notice notice-ok" role="status">{msg}</div>}
      {err && <div className="notice notice-danger" role="alert">{err}</div>}
      <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))" }} aria-label="Resumen de caja">
        {([["Saldo al empezar el día", d.cash.opening_cents], ["Entradas en efectivo", d.cash.in_cents], ["Salidas en efectivo", d.cash.out_cents], ["Saldo según registros", d.cash.balance_cents]] as const).map(([l, v]) => (
          <div key={l} className="card" style={{ padding: 14 }}><div className="stat" style={{ fontSize: "1.4rem" }}>{fmtMoney(v, d.currency)}</div><div className="stat-label">{l}</div></div>
        ))}
        <div className="card" style={{ padding: 14 }}><div className="stat" style={{ fontSize: "1.4rem" }}>{d.totals.cobros}</div><div className="stat-label">Cobros · {fmtMoney(d.totals.importe_cents, d.currency)}</div>
          <div className="small muted">{Object.entries(d.totals.por_forma).map(([k, v]) => `${label(METODOS_COBRO, k)} ${fmtMoney(v, d.currency)}`).join(" · ") || "—"}</div></div>
      </div>
      <div className="card">
        <h2>Cobros del día</h2>
        <div className="table-wrap">
          <table className="data">
            <thead><tr><th>Hora</th><th>Cliente</th><th>Concepto</th><th>Forma</th><th style={{ textAlign: "right" }}>Importe</th><th>Justificante</th></tr></thead>
            <tbody>
              {d.payments.length === 0 && <tr><td colSpan={6} className="empty">Sin cobros este día.</td></tr>}
              {d.payments.map((x) => (
                <tr key={x.id} style={x.status === "anulado" ? { opacity: 0.55, textDecoration: "line-through" } : undefined}>
                  <td>{fmtTime(x.received_at)}</td>
                  <td>{x.contact_name}<div className="small muted">{x.registered_by}</div></td>
                  <td>{KINDS[x.kind ?? ""] ?? "Cobro"}{x.case_code ? <> · <span className="mono">{x.case_code}</span></> : ""}
                    {x.duplicate_reason && <div className="small"><span className="badge badge-yellow">parecía repetido</span> {x.duplicate_reason}</div>}
                    {x.status === "anulado" && <div className="small"><span className="badge badge-red">anulado</span></div>}</td>
                  <td>{label(METODOS_COBRO, x.method)}{x.reference ? <div className="small muted">{x.reference}</div> : null}</td>
                  <td style={{ textAlign: "right" }}><strong>{fmtMoney(x.amount_cents, x.currency)}</strong></td>
                  <td>{x.receipt ? <a href={`/api/v1${x.receipt.url}`} target="_blank" rel="noreferrer" className="mono small">{x.receipt.number}</a> : <span className="small muted">—</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <div className="card stack" style={{ gap: 10 }}>
        <h2 style={{ margin: 0 }}>Cierre del día</h2>
        {d.closings.map((c) => (
          <div key={c.id} className={`notice ${c.status === "validado" ? "notice-ok" : c.status === "rechazado" ? "notice-danger" : "notice-warn"}`}>
            <strong><span className={`badge ${CLOSE_ST[c.status][1]}`}>{CLOSE_ST[c.status][0]}</span> Contado {fmtMoney(c.counted_cents, d.currency)} · esperado {fmtMoney(c.expected_cents, d.currency)} · diferencia {fmtMoney(c.difference_cents, d.currency)}</strong>
            Cerró {c.closed_by} a las {fmtTime(c.closed_at)}{c.notes ? ` · «${c.notes}»` : ""}{c.validated_by ? ` · ${c.status === "validado" ? "validó" : "rechazó"} ${c.validated_by}${c.validation_note ? `: «${c.validation_note}»` : ""}` : ""}
          </div>
        ))}
        {d.can_close ? (
          <form className="stack" style={{ gap: 8 }} onSubmit={close} aria-label="Cerrar caja">
            <p className="small muted" style={{ margin: 0 }}>Cuente el efectivo de la caja y anótelo. La diferencia se calcula sola; si la hay, explique el motivo. Un responsable validará el cierre.</p>
            <div className="row">
              <div style={{ maxWidth: 220 }}><MoneyInput label="Efectivo contado" value={counted} onChange={setCounted} /></div>
              {diff !== null && <span className={`badge ${diff === 0 ? "badge-green" : "badge-red"}`} aria-label="Diferencia">{diff === 0 ? "Cuadra" : `Diferencia ${fmtMoney(diff, d.currency)}`}</span>}
            </div>
            {diff !== null && diff !== 0 && <label className="field">Motivo de la diferencia *<input value={note} onChange={(e) => setNote(e.target.value)} minLength={5} required /></label>}
            <div><button className="btn btn-primary" disabled={countedCents === null}>Cerrar la caja de hoy</button></div>
          </form>
        ) : (!d.closings.some((c) => c.status !== "rechazado") && <p className="small muted" style={{ margin: 0 }}>{d.is_today ? "Solo la recepción de esta sede cierra su caja." : "Día pasado sin cierre registrado."}</p>)}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ informe
interface ReportDay { day: string; cobros: number; importe_cents: number; por_tipo: Record<string, number>; por_forma: Record<string, number>; anulados: number; posibles_duplicados: number; devoluciones_efectivo_cents: number; cierre: { estado: string; diferencia_cents: number } | null }
interface ReportRes { branches: { branch_id: string; branch: string; currency: string; days: ReportDay[]; total: { cobros: number; importe_cents: number; dias_sin_cierre: number; diferencias_cents: number } }[]; no_disponible: string }

function Report({ b, all }: { b: BranchInfo; all: BranchInfo[] }) {
  const today = madridDay(new Date());
  const [from, setFrom] = useState(today);
  const [to, setTo] = useState(today);
  const [only, setOnly] = useState(all.length > 1 ? "" : b.id);
  const [r, setR] = useState<ReportRes | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { api<ReportRes>(`/reception/report?from=${from}&to=${to}${only ? `&branch_id=${only}` : ""}`).then((x) => { setR(x); setErr(null); }).catch((e) => setErr(errMsg(e))); }, [from, to, only]);
  const week = () => { const d = new Date(); d.setDate(d.getDate() - 6); setFrom(madridDay(d)); setTo(today); };
  return (
    <div className="stack">
      <div className="row">
        <button className="btn btn-sm" onClick={() => { setFrom(today); setTo(today); }}>Hoy</button>
        <button className="btn btn-sm" onClick={week}>Últimos 7 días</button>
        <input type="date" aria-label="Desde" value={from} onChange={(e) => setFrom(e.target.value)} style={{ width: "auto" }} />
        <input type="date" aria-label="Hasta" value={to} onChange={(e) => setTo(e.target.value)} style={{ width: "auto" }} />
        {all.length > 1 && (
          <select aria-label="Sedes del informe" value={only} onChange={(e) => setOnly(e.target.value)} style={{ width: "auto" }}>
            <option value="">Todas mis sedes</option>{all.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
          </select>
        )}
      </div>
      {err && <div className="notice notice-danger">{err}</div>}
      {r?.branches.map((s) => (
        <div key={s.branch_id} className="card">
          <div className="row"><h2 style={{ margin: 0 }}>{s.branch}</h2><span className="spacer" />
            <span className="small">{s.total.cobros} cobros · <strong>{fmtMoney(s.total.importe_cents, s.currency)}</strong>{s.total.dias_sin_cierre ? <> · <span className="badge badge-red">{s.total.dias_sin_cierre} día(s) sin cierre</span></> : ""}{s.total.diferencias_cents ? <> · diferencias {fmtMoney(s.total.diferencias_cents, s.currency)}</> : ""}</span></div>
          <div className="table-wrap" style={{ marginTop: 10 }}>
            <table className="data">
              <thead><tr><th>Día</th><th>Cobros</th><th>Por concepto</th><th>Por forma de pago</th><th>Incidencias</th><th>Cierre</th></tr></thead>
              <tbody>{s.days.map((x) => (
                <tr key={x.day}>
                  <td>{fmtDate(x.day)}</td>
                  <td>{x.cobros} · <strong>{fmtMoney(x.importe_cents, s.currency)}</strong></td>
                  <td className="small">{Object.entries(x.por_tipo).map(([k, v]) => `${KINDS[k] ?? k}: ${v}`).join(" · ") || "—"}</td>
                  <td className="small">{Object.entries(x.por_forma).map(([k, v]) => `${label(METODOS_COBRO, k)} ${fmtMoney(v, s.currency)}`).join(" · ") || "—"}</td>
                  <td className="small">{[x.anulados ? `${x.anulados} anulado(s)` : "", x.posibles_duplicados ? `${x.posibles_duplicados} parecía(n) repetido(s)` : "", x.devoluciones_efectivo_cents ? `devoluciones ${fmtMoney(x.devoluciones_efectivo_cents, s.currency)}` : ""].filter(Boolean).join(" · ") || "—"}</td>
                  <td>{x.cierre ? <span className={`badge ${CLOSE_ST[x.cierre.estado]?.[1] ?? ""}`}>{CLOSE_ST[x.cierre.estado]?.[0]}{x.cierre.diferencia_cents ? ` · ${fmtMoney(x.cierre.diferencia_cents, s.currency)}` : ""}</span> : (x.cobros ? <span className="badge badge-red">Sin cierre</span> : "—")}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </div>
      ))}
      {r && <p className="small muted">{r.no_disponible}</p>}
    </div>
  );
}

export default function Page() {
  return <Suspense fallback={<p className="muted">Cargando…</p>}><Recepcion /></Suspense>;
}

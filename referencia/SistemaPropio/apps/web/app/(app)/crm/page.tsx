"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { useMe } from "@/components/session";
import { LeadStatusBadge, Pager } from "@/components/ui";
import { api, ApiError, fieldErrors, hasPerm, type Contact, type Funnel, type Lead, type Organization, type Origin, type Page } from "@/lib/api";
import { fmtDateTime, label, LEAD_ESTADOS, MATERIAS_LEAD } from "@/lib/format";

const FOLLOW = ["", "Más de 24 h sin avanzar", "Más de 72 h sin avanzar", "Más de 7 días sin avanzar"];

function CrmInner() {
  const me = useMe();
  const params = useSearchParams();
  const router = useRouter();
  const [tab, setTab] = useState<"bandeja" | "seguimiento" | "nuevo" | "embudo">(params.get("nuevo") ? "nuevo" : "bandeja");
  const [status, setStatus] = useState("");
  const [origin, setOrigin] = useState("");
  const [mine, setMine] = useState(false);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Page<Lead> | null>(null);
  const [origins, setOrigins] = useState<Origin[]>([]);
  const [error, setError] = useState<string | null>(null);

  const canRead = hasPerm(me, "lead.read.all") || hasPerm(me, "lead.read.own");
  const load = useCallback(() => {
    if (!canRead || tab === "nuevo" || tab === "embudo") return;
    const qs = new URLSearchParams({ page: String(page), page_size: "25" });
    if (tab === "seguimiento") qs.set("follow_up", "true");
    if (status) qs.set("status", status);
    if (origin) qs.set("origin", origin);
    if (mine) qs.set("mine", "true");
    api<Page<Lead>>(`/leads?${qs}`).then(setData).catch((e) => setError(e instanceof ApiError ? e.message : "Error"));
  }, [canRead, tab, page, status, origin, mine]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { api<Origin[]>("/leads/origins").then(setOrigins).catch(() => undefined); }, []);

  if (!canRead) return <div className="notice notice-warn"><strong>Sin acceso</strong>Su rol no trabaja con el CRM.</div>;

  return (
    <div className="stack">
      <div className="topline">
        <div>
          <h1>CRM</h1>
          <p className="subtitle">Cada lead nace con su origen y se vincula al cliente maestro. Cuando se abre su expediente queda convertido y trazable.</p>
        </div>
        {hasPerm(me, "lead.create") && tab !== "nuevo" && <button className="btn btn-primary" onClick={() => setTab("nuevo")}>+ Nuevo lead</button>}
      </div>
      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === "bandeja"} onClick={() => { setTab("bandeja"); setPage(1); }}>Bandeja</button>
        <button role="tab" aria-selected={tab === "seguimiento"} onClick={() => { setTab("seguimiento"); setPage(1); }}>Pendientes de seguimiento</button>
        {hasPerm(me, "lead.create") && <button role="tab" aria-selected={tab === "nuevo"} onClick={() => setTab("nuevo")}>Nuevo lead</button>}
        {hasPerm(me, "lead.funnel") && <button role="tab" aria-selected={tab === "embudo"} onClick={() => setTab("embudo")}>Embudo</button>}
      </div>
      {error && <div className="notice notice-danger">{error}</div>}

      {tab === "nuevo" && <NewLead origins={origins} presetContact={params.get("contact")} onCreated={(id) => router.push(`/crm/${id}`)} />}
      {tab === "embudo" && <FunnelView />}

      {(tab === "bandeja" || tab === "seguimiento") && (
        <>
          {tab === "seguimiento" && (
            <div className="notice notice-info">Leads abiertos que llevan más de 24 horas sin avanzar, ordenados del más antiguo al más reciente (control de TikTok Live y resto de canales).</div>
          )}
          {tab === "bandeja" && (
            <div className="row">
              <label className="field" style={{ maxWidth: 220 }}>Estado
                <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
                  <option value="">Todos</option>
                  {Object.entries(LEAD_ESTADOS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
              </label>
              <label className="field" style={{ maxWidth: 240 }}>Origen
                <select value={origin} onChange={(e) => { setOrigin(e.target.value); setPage(1); }}>
                  <option value="">Todos</option>
                  {origins.map((o) => <option key={o.code} value={o.code}>{o.name}</option>)}
                </select>
              </label>
              <label className="row" style={{ marginTop: 20 }}><input type="checkbox" style={{ width: "auto" }} checked={mine} onChange={(e) => { setMine(e.target.checked); setPage(1); }} /> Solo asignados a mí</label>
            </div>
          )}
          <div className="table-wrap">
            <table className="data">
              <thead><tr><th>Persona</th><th>Origen</th><th>Materia</th><th>Estado</th><th>Último cambio</th><th>Asignado</th><th>Expediente</th></tr></thead>
              <tbody>
                {!data && <tr><td colSpan={7} className="empty">Cargando…</td></tr>}
                {data?.items.length === 0 && <tr><td colSpan={7} className="empty">No hay leads con estos filtros.</td></tr>}
                {data?.items.map((l) => (
                  <tr key={l.id} className="clickable" onClick={() => router.push(`/crm/${l.id}`)}>
                    <td><Link href={`/crm/${l.id}`} onClick={(e) => e.stopPropagation()}><strong>{l.contact_name}</strong></Link>
                      <div className="small muted mono">{l.contact_phone_masked ?? ""}</div></td>
                    <td>{l.origin_name}{l.campaign && <div className="small muted">{l.campaign}</div>}</td>
                    <td>{label(MATERIAS_LEAD, l.materia)}</td>
                    <td><LeadStatusBadge s={l.status} />{l.follow_up_level > 0 && <div><span className={`badge ${l.follow_up_level >= 2 ? "badge-red" : "badge-yellow"}`} style={{ marginTop: 4 }}>{FOLLOW[l.follow_up_level]}</span></div>}</td>
                    <td>{fmtDateTime(l.status_changed_at)}</td>
                    <td className="mono">{l.assigned_username ?? <span className="muted">Sin asignar</span>}</td>
                    <td className="mono">{l.case_code ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {data && <Pager page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />}
        </>
      )}
    </div>
  );
}

function NewLead({ origins, presetContact, onCreated }: { origins: Origin[]; presetContact: string | null; onCreated: (id: string) => void }) {
  const me = useMe();
  const [orgs, setOrgs] = useState<Organization[]>([]);
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Contact[] | null>(null);
  const [contact, setContact] = useState<{ id: string; name: string } | null>(null);
  const [f, setF] = useState({ organization_id: "", branch_id: "", origin_code: "", materia: "laboral", campaign: "", utm_source: "", utm_medium: "", utm_campaign: "", summary: "" });
  const [errs, setErrs] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState<string | null>(null);
  const [searchMsg, setSearchMsg] = useState<string | null>(null);

  useEffect(() => {
    api<Organization[]>("/organizations").then((o) => {
      const allowed = o.filter((x) => (me.permissions[x.id] ?? []).includes("lead.create"));
      setOrgs(allowed);
      if (allowed[0]) setF((s) => ({ ...s, organization_id: allowed[0].id }));
    });
    if (presetContact) api<Contact>(`/contacts/${presetContact}`).then((c) => setContact({ id: c.id, name: c.display_name })).catch(() => undefined);
  }, [me, presetContact]);

  async function search(e: React.FormEvent) {
    e.preventDefault();
    setSearchMsg(null);
    try { setResults((await api<Page<Contact>>(`/contacts?q=${encodeURIComponent(q)}&page_size=10`)).items); }
    catch (err) { setResults(null); setSearchMsg(err instanceof ApiError ? err.message : "Error al buscar"); }
  }
  const origin = origins.find((o) => o.code === f.origin_code);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setF((s) => ({ ...s, [k]: e.target.value }));

  async function save() {
    setMsg(null); setErrs({});
    if (!contact) { setErrs({ contact_id: "Elija o dé de alta a la persona primero." }); return; }
    const body: Record<string, unknown> = { ...f, contact_id: contact.id, branch_id: f.branch_id || null };
    for (const k of ["campaign", "utm_source", "utm_medium", "utm_campaign"]) if (!body[k]) body[k] = null;
    if (!f.origin_code) delete body.origin_code;
    try { const l = await api<Lead>("/leads", { method: "POST", body: JSON.stringify(body) }); onCreated(l.id); }
    catch (e) { setMsg(e instanceof ApiError ? e.message : "No se pudo guardar"); setErrs(fieldErrors(e)); }
  }
  const org = orgs.find((o) => o.id === f.organization_id);

  return (
    <div className="stack">
      {msg && <div className="notice notice-danger" role="alert">{msg}</div>}
      <fieldset>
        <legend>1. Persona</legend>
        {contact ? (
          <div className="row"><strong>{contact.name}</strong><button className="btn btn-sm" onClick={() => setContact(null)}>Cambiar</button></div>
        ) : (
          <div className="stack" style={{ gap: 10 }}>
            <form className="search" onSubmit={search}><input aria-label="Buscar persona" placeholder="Nombre, teléfono o documento (mín. 3 caracteres)" value={q} onChange={(e) => setQ(e.target.value)} /><button className="btn" type="submit">Buscar</button></form>
            {searchMsg && <span className="error-text">{searchMsg}</span>}
            {results && (results.length ? (
              <div className="stack" style={{ gap: 6 }}>{results.map((c) => (
                <button key={c.id} className="user-option" onClick={() => setContact({ id: c.id, name: c.display_name })}>
                  <strong>{c.display_name}</strong><span className="muted small">{c.access_level === "full" && "points" in c ? c.points.filter((p) => p.kind === "phone").map((p) => p.value_normalized).join(", ") : c.phones_masked.join(", ")} · {c.primary_branch ?? "sin sede"}</span>
                </button>))}</div>
            ) : <p className="muted">No existe. <Link href="/clientes/nuevo">Dar de alta a la persona</Link> y vuelva aquí.</p>)}
            {errs.contact_id && <span className="error-text">{errs.contact_id}</span>}
          </div>
        )}
      </fieldset>
      <fieldset>
        <legend>2. Origen y consulta</legend>
        <div className="form-grid">
          {orgs.length > 1 && <label className="field">Entidad<select value={f.organization_id} onChange={set("organization_id")}>{orgs.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}</select></label>}
          <label className="field">Origen *<select value={f.origin_code} onChange={set("origin_code")} className={errs.origin_code ? "invalid" : ""}>
            <option value="">Elija el canal…</option>{origins.map((o) => <option key={o.code} value={o.code}>{o.name}</option>)}</select>
            {errs.origin_code && <span className="error-text">{errs.origin_code}</span>}</label>
          <label className="field">Materia<select value={f.materia} onChange={set("materia")}>{Object.entries(MATERIAS_LEAD).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
          <label className="field">Sede<select value={f.branch_id} onChange={set("branch_id")}><option value="">Sin asignar</option>{org?.branches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}</select></label>
          <label className="field">Campaña {origin?.requires_campaign && "*"}<input value={f.campaign} onChange={set("campaign")} className={errs.campaign ? "invalid" : ""} />
            {errs.campaign && <span className="error-text">{errs.campaign}</span>}</label>
          <label className="field">UTM source<input value={f.utm_source} onChange={set("utm_source")} /></label>
          <label className="field">UTM medium<input value={f.utm_medium} onChange={set("utm_medium")} /></label>
          <label className="field">UTM campaign<input value={f.utm_campaign} onChange={set("utm_campaign")} /></label>
          <label className="field full">Motivo de la consulta <span className="hint">Lo que cuenta la persona. No anote aquí valoraciones jurídicas.</span>
            <textarea rows={3} value={f.summary} onChange={set("summary")} /></label>
        </div>
      </fieldset>
      <div className="row"><button className="btn btn-primary" onClick={save}>Registrar lead</button><span className="small muted">El origen es obligatorio. TikTok Live y Google Ads exigen campaña.</span></div>
    </div>
  );
}

function FunnelView() {
  const [f, setF] = useState<Funnel | null>(null);
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  useEffect(() => {
    const qs = new URLSearchParams();
    if (desde) qs.set("desde", desde);
    if (hasta) qs.set("hasta", hasta);
    api<Funnel>(`/leads/funnel?${qs}`).then(setF).catch(() => setF(null));
  }, [desde, hasta]);
  const order = ["nuevo", "contactado", "en_seguimiento", "cita_solicitada", "convertido", "no_convertido", "descartado"];
  const max = Math.max(1, ...Object.values(f?.por_estado ?? {}));
  return (
    <div className="stack">
      <div className="row">
        <label className="field" style={{ maxWidth: 200 }}>Desde<input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} /></label>
        <label className="field" style={{ maxWidth: 200 }}>Hasta<input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} /></label>
      </div>
      {f && (
        <>
          <div className="grid grid-3">
            <div className="card"><div className="stat-label">Leads</div><div className="stat">{f.total}</div></div>
            <div className="card"><div className="stat-label">Convertidos en expediente</div><div className="stat">{f.convertidos}</div></div>
            <div className="card"><div className="stat-label">Conversión</div><div className="stat">{(f.conversion * 100).toFixed(1)} %</div></div>
          </div>
          <div className="grid grid-2">
            <div className="card">
              <h2>Por estado</h2>
              <div className="stack" style={{ gap: 8 }}>
                {order.map((s) => (
                  <div key={s} className="row" style={{ flexWrap: "nowrap" }}>
                    <span style={{ width: 130, flex: "none" }} className="small">{label(LEAD_ESTADOS, s)}</span>
                    <div style={{ flex: 1, background: "var(--surface-2)", borderRadius: 6, height: 18 }}>
                      <div style={{ width: `${((f.por_estado[s] ?? 0) / max) * 100}%`, background: s === "convertido" ? "var(--ok)" : "var(--primary)", height: "100%", borderRadius: 6 }} />
                    </div>
                    <span className="mono" style={{ width: 32, textAlign: "right" }}>{f.por_estado[s] ?? 0}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="card">
              <h2>Por origen</h2>
              <table className="data"><thead><tr><th>Origen</th><th>Leads</th><th>Convertidos</th><th>%</th></tr></thead>
                <tbody>{f.por_origen.map((o) => <tr key={o.origin}><td>{o.name}</td><td className="mono">{o.total}</td><td className="mono">{o.convertidos}</td><td className="mono">{(o.conversion * 100).toFixed(0)} %</td></tr>)}</tbody></table>
            </div>
          </div>
          <p className="small muted">{f.nota}</p>
        </>
      )}
    </div>
  );
}

export default function CrmPage() {
  return <Suspense fallback={<p className="muted">Cargando…</p>}><CrmInner /></Suspense>;
}

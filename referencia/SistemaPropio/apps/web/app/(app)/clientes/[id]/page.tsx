"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { CommThreadPanel, PortalAccessCard } from "@/components/comm";
import { useMe } from "@/components/session";
import { AccessBadge, EstadoBadge, LeadStatusBadge, MateriaBadge } from "@/components/ui";
import { api, ApiError, fieldErrors, type AuditEvent, type CaseMeta, type Contact, type ContactFull, type Lead, type Page } from "@/lib/api";
import { ACCIONES_AUDITORIA, fmtDate, fmtDateTime, label } from "@/lib/format";

type Tab = "datos" | "contactos" | "expedientes" | "leads" | "historial" | "portal";

function Detail() {
  const { id } = useParams<{ id: string }>();
  const params = useSearchParams();
  const me = useMe();
  const [c, setC] = useState<Contact | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [tab, setTab] = useState<Tab>("datos");
  const [cases, setCases] = useState<CaseMeta[] | null>(null);
  const [history, setHistory] = useState<AuditEvent[] | null>(null);
  const [historyDenied, setHistoryDenied] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [leads, setLeads] = useState<Lead[] | null>(null);
  const [leadsMsg, setLeadsMsg] = useState<string | null>(null);

  const load = useCallback(() => {
    api<Contact>(`/contacts/${id}`).then(setC).catch((e) => { if (e instanceof ApiError && e.status === 404) setNotFound(true); });
  }, [id]);
  useEffect(load, [load]);

  useEffect(() => {
    if (tab === "expedientes" && cases === null) api<CaseMeta[]>(`/contacts/${id}/cases`).then(setCases).catch(() => setCases([]));
    if (tab === "leads" && leads === null) {
      api<Page<Lead>>(`/leads?contact_id=${id}&page_size=50`).then((r) => setLeads(r.items))
        .catch((e) => { setLeads([]); setLeadsMsg(e instanceof ApiError ? e.message : "No disponible"); });
    }
    if (tab === "historial") {
      api<AuditEvent[]>(`/contacts/${id}/history`).then(setHistory)
        .catch((e) => setHistoryDenied(e instanceof ApiError ? e.message : "No disponible."));
    }
  }, [tab, id, cases, leads]);

  if (notFound) return <div className="notice notice-warn"><strong>Contacto no encontrado</strong>No existe o está fuera de su ámbito. <Link href="/clientes">Volver</Link></div>;
  if (!c) return <p className="muted">Cargando ficha…</p>;
  const full = c.access_level === "full" ? (c as ContactFull) : null;
  const perms = me.permissions[c.organization_id] ?? [];
  const canEdit = !!full && perms.includes("contact.update");

  return (
    <div className="stack">
      <div className="topline">
        <div>
          <p className="small muted" style={{ margin: 0 }}><Link href="/clientes">Clientes</Link> / ficha</p>
          <h1>{c.display_name}</h1>
          <div className="row">
            <AccessBadge level={c.access_level} />
            {c.possible_duplicate && <span className="badge badge-yellow">Posible duplicado en revisión</span>}
            {full?.is_synthetic && <span className="badge">Dato ficticio</span>}
          </div>
        </div>
        <div className="row">
          {perms.includes("lead.create") && <Link className="btn" href={`/crm?nuevo=1&contact=${c.id}`}>Nuevo lead</Link>}
          {perms.includes("case.create") && <Link className="btn" href={`/expedientes/nuevo?contact=${c.id}`}>Abrir expediente</Link>}
          {canEdit && !editing && <button className="btn" onClick={() => { setEditing(true); setTab("datos"); }}>Editar datos</button>}
        </div>
      </div>
      {params.get("alta") && <div className="notice notice-ok" role="status"><strong>Cliente dado de alta</strong>El alta ha quedado registrada en la auditoría.</div>}
      {!full && (
        <div className="notice notice-info">
          <strong>Ficha mínima</strong>
          Su perfil puede identificar a esta persona, pero no ver sus datos completos ni el contenido de sus expedientes.
        </div>
      )}

      <div className="tabs" role="tablist">
        {(["datos", "contactos", "expedientes", "leads", "historial", ...(full && perms.includes("comm.read") ? ["portal"] : [])] as Tab[]).map((t) => (
          <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}>
            {{ datos: "Datos", contactos: "Contactos", expedientes: "Expedientes autorizados", leads: "Leads", historial: "Historial", portal: "Portal y mensajes" }[t]}
          </button>
        ))}
      </div>

      {tab === "datos" && (editing && full
        ? <EditForm c={full} onDone={(updated) => { setEditing(false); if (updated) setC(updated); }} />
        : (
          <div className="card">
            <dl className="kv">
              <dt>Nombre</dt><dd>{c.display_name}</dd>
              <dt>Sede principal</dt><dd>{c.primary_branch ?? "—"}</dd>
              <dt>Documentos</dt><dd className="mono">{full ? full.identifiers.map((i) => `${i.kind} ${i.number_normalized} (${i.country})`).join(" · ") || "—" : c.identifiers_masked.join(" · ") || "—"}</dd>
              {full && <>
                <dt>Fecha de nacimiento</dt><dd>{fmtDate(full.birth_date)}</dd>
                <dt>Nacionalidad</dt><dd>{full.nationality ?? "—"}</dd>
                <dt>Idioma</dt><dd>{full.preferred_language}</dd>
                <dt>Canal de entrada</dt><dd>{full.origin ?? "—"}</dd>
                <dt>Consentimientos</dt><dd>{full.consents.map((x) => `${x.purpose.replaceAll("_", " ")}: ${x.granted ? "sí" : "no"} (${x.source}, ${fmtDateTime(x.recorded_at)})`).join(" · ") || "—"}</dd>
                <dt>Alta</dt><dd>{fmtDateTime(full.created_at)}</dd>
                <dt>Última modificación</dt><dd>{fmtDateTime(full.updated_at)} · versión {full.version}</dd>
              </>}
            </dl>
          </div>
        ))}

      {tab === "portal" && full && (
        <div className="stack">
          <PortalAccessCard contactId={c.id} />
          <CommThreadPanel contactId={c.id} compact />
        </div>
      )}

      {tab === "contactos" && (
        <div className="card">
          {full ? (
            <dl className="kv">
              <dt>Teléfonos</dt><dd className="mono">{full.points.filter((p) => p.kind === "phone").map((p) => `${p.value_normalized}${p.is_primary ? " (principal)" : ""}`).join(" · ") || "—"}</dd>
              <dt>Correos</dt><dd>{full.points.filter((p) => p.kind === "email").map((p) => p.value_normalized).join(" · ") || "—"}</dd>
              <dt>Domicilios</dt><dd>{full.addresses.map((a) => `${a.kind}: ${a.line1}${a.postal_code ? `, ${a.postal_code}` : ""} ${a.municipality}`).join(" · ") || "—"}</dd>
            </dl>
          ) : (
            <dl className="kv"><dt>Teléfonos</dt><dd className="mono">{c.phones_masked.join(" · ") || "—"}</dd></dl>
          )}
        </div>
      )}

      {tab === "expedientes" && (
        <div className="table-wrap">
          <table className="data">
            <thead><tr><th>Código</th><th>Materia</th><th>Estado</th><th>Sede</th><th>Acceso</th></tr></thead>
            <tbody>
              {cases === null && <tr><td colSpan={5} className="empty">Cargando…</td></tr>}
              {cases?.length === 0 && <tr><td colSpan={5} className="empty">No hay expedientes que su perfil pueda ver.</td></tr>}
              {cases?.map((x) => (
                <tr key={x.id}>
                  <td className="mono">{x.access_level === "full" ? <Link href={`/expedientes/${x.id}`}>{x.code}</Link> : x.code}</td>
                  <td><MateriaBadge materia={x.materia} /></td>
                  <td><EstadoBadge status={x.status} /></td>
                  <td>{x.branch}</td>
                  <td><AccessBadge level={x.access_level} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === "leads" && (
        leadsMsg ? <div className="notice notice-info"><strong>Sin acceso al CRM</strong>{leadsMsg}</div> : (
          <div className="table-wrap">
            <table className="data">
              <thead><tr><th>Alta</th><th>Origen</th><th>Estado</th><th>Expediente</th></tr></thead>
              <tbody>
                {leads === null && <tr><td colSpan={4} className="empty">Cargando…</td></tr>}
                {leads?.length === 0 && <tr><td colSpan={4} className="empty">No hay leads visibles para esta persona.</td></tr>}
                {leads?.map((l) => (
                  <tr key={l.id}><td><Link href={`/crm/${l.id}`}>{fmtDateTime(l.created_at)}</Link></td><td>{l.origin_name}</td>
                    <td><LeadStatusBadge s={l.status} /></td><td className="mono">{l.case_code ?? "—"}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}

      {tab === "historial" && (
        historyDenied ? <div className="notice notice-info"><strong>Historial restringido</strong>{historyDenied}</div> : (
          <div className="table-wrap">
            <table className="data">
              <thead><tr><th>Fecha (Madrid)</th><th>Usuario</th><th>Acción</th><th>Resultado</th><th>Detalle</th></tr></thead>
              <tbody>
                {history === null && <tr><td colSpan={5} className="empty">Cargando…</td></tr>}
                {history?.map((e) => (
                  <tr key={e.id}>
                    <td>{fmtDateTime(e.occurred_at)}</td>
                    <td>{e.actor_username ?? "sistema"}</td>
                    <td>{label(ACCIONES_AUDITORIA, e.action)}</td>
                    <td>{e.outcome === "ok" ? <span className="badge badge-green">Correcto</span> : <span className="badge badge-red">Denegado</span>}</td>
                    <td className="small">{e.reason ? <div>Motivo: {e.reason}</div> : null}
                      {e.before && <div className="mono">antes: {JSON.stringify(e.before)}</div>}
                      {e.after && <div className="mono">después: {JSON.stringify(e.after)}</div>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}
    </div>
  );
}

function EditForm({ c, onDone }: { c: ContactFull; onDone: (u: ContactFull | null) => void }) {
  const [given, setGiven] = useState(c.given_name);
  const [family, setFamily] = useState(c.family_names);
  const [lang, setLang] = useState(c.preferred_language);
  const [phone, setPhone] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [fe, setFe] = useState<Record<string, string>>({});

  async function save() {
    setError(null);
    const body: Record<string, unknown> = { version: c.version, reason };
    if (given !== c.given_name) body.given_name = given;
    if (family !== c.family_names) body.family_names = family;
    if (lang !== c.preferred_language) body.preferred_language = lang;
    if (phone.trim()) body.add_phones = [{ number: phone, label: "movil" }];
    try {
      onDone(await api<ContactFull>(`/contacts/${c.id}`, { method: "PATCH", body: JSON.stringify(body) }));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo guardar.");
      setFe(fieldErrors(e));
    }
  }

  return (
    <div className="card stack">
      {error && <div className="notice notice-danger" role="alert">{error}</div>}
      <div className="form-grid">
        <label className="field">Nombre<input value={given} onChange={(e) => setGiven(e.target.value)} /></label>
        <label className="field">Apellidos<input value={family} onChange={(e) => setFamily(e.target.value)} /></label>
        <label className="field">Idioma
          <select value={lang} onChange={(e) => setLang(e.target.value)}>
            {["es", "ca", "en", "fr", "ar", "ro", "pt"].map((l) => <option key={l} value={l}>{l}</option>)}
          </select>
        </label>
        <label className="field">Añadir teléfono<input value={phone} onChange={(e) => setPhone(e.target.value)} inputMode="tel" />
          {fe.phone && <span className="error-text">{fe.phone}</span>}</label>
        <label className="field full">Motivo del cambio * <span className="hint">Queda en la auditoría junto al dato anterior y el nuevo.</span>
          <input value={reason} onChange={(e) => setReason(e.target.value)} />
          {fe.reason && <span className="error-text">{fe.reason}</span>}</label>
      </div>
      <div className="row">
        <button className="btn btn-primary" onClick={save} disabled={reason.trim().length < 3}>Guardar cambios</button>
        <button className="btn" onClick={() => onDone(null)}>Cancelar</button>
      </div>
    </div>
  );
}

export default function ClientePage() {
  return <Suspense fallback={<p className="muted">Cargando…</p>}><Detail /></Suspense>;
}

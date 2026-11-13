"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { useMe } from "@/components/session";
import { LeadStatusBadge } from "@/components/ui";
import { api, ApiError, permsIn, type LeadDetail } from "@/lib/api";
import { ACCION_LEAD, fmtDateTime, label, LEAD_ESTADOS, MATERIAS_LEAD } from "@/lib/format";

const NEEDS_NOTE = new Set(["descartado", "no_convertido"]);

export default function LeadPage() {
  const { id } = useParams<{ id: string }>();
  const me = useMe();
  const [lead, setLead] = useState<LeadDetail | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [pending, setPending] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const load = useCallback(() => {
    api<LeadDetail>(`/leads/${id}`).then(setLead).catch((e) => { if (e instanceof ApiError && e.status === 404) setNotFound(true); });
  }, [id]);
  useEffect(load, [load]);

  if (notFound) return <div className="notice notice-warn"><strong>Lead no encontrado</strong>No existe o está fuera de su ámbito. <Link href="/crm">Volver</Link></div>;
  if (!lead) return <p className="muted">Cargando lead…</p>;

  const reopening = lead.status === "descartado" || lead.status === "no_convertido";
  const needsNote = (to: string) => NEEDS_NOTE.has(to) || reopening;
  const canOpenCase = permsIn(me, lead.organization_id).includes("case.create")
    && !["convertido", "descartado"].includes(lead.status) && lead.materia !== "otra";

  async function go(to: string) {
    if (needsNote(to) && note.trim().length < 5) { setPending(to); setMsg({ ok: false, text: "Indique el motivo (mín. 5 caracteres)." }); return; }
    try {
      await api(`/leads/${id}/transition`, { method: "POST", body: JSON.stringify({ to, version: lead!.version, note: note.trim() || null }) });
      setMsg({ ok: true, text: `Estado cambiado a «${label(LEAD_ESTADOS, to)}». Queda en el historial y en la auditoría.` });
      setNote(""); setPending(null); load();
    } catch (e) { setMsg({ ok: false, text: e instanceof ApiError ? e.message : "No se pudo cambiar" }); }
  }

  return (
    <div className="stack">
      <div className="topline">
        <div>
          <p className="small muted" style={{ margin: 0 }}><Link href="/crm">CRM</Link> / lead</p>
          <h1>{lead.contact_name}</h1>
          <div className="row"><LeadStatusBadge s={lead.status} /><span className="badge">{lead.origin_name}</span><span className="badge">{label(MATERIAS_LEAD, lead.materia)}</span></div>
        </div>
        <div className="row">
          <Link className="btn" href={`/clientes/${lead.contact_id}`}>Ver ficha del cliente</Link>
          {canOpenCase && <Link className="btn btn-primary" href={`/expedientes/nuevo?lead=${lead.id}&contact=${lead.contact_id}&materia=${lead.materia}`}>Abrir expediente</Link>}
        </div>
      </div>
      {msg && <div className={`notice ${msg.ok ? "notice-ok" : "notice-danger"}`} role="status">{msg.text}</div>}

      <div className="grid grid-2">
        <div className="card">
          <h2>Datos del lead</h2>
          <dl className="kv">
            <dt>Teléfono</dt><dd className="mono">{lead.contact_phone_masked ?? "—"}</dd>
            <dt>Origen</dt><dd>{lead.origin_name}{lead.campaign ? ` · ${lead.campaign}` : ""}</dd>
            <dt>UTM</dt><dd className="mono small">{Object.entries(lead.utm).filter(([, v]) => v).map(([k, v]) => `${k}=${v}`).join(" · ") || "—"}</dd>
            <dt>Sede</dt><dd>{lead.branch ?? "—"}</dd>
            <dt>Asignado a</dt><dd className="mono">{lead.assigned_username ?? "Sin asignar"}</dd>
            <dt>Alta</dt><dd>{fmtDateTime(lead.created_at)}</dd>
            <dt>Motivo de consulta</dt><dd>{lead.summary || "—"}</dd>
            <dt>Expediente</dt><dd>{lead.case_code ? (lead.case_access === "full" ? <Link href={`/expedientes/${lead.case_file_id}`}>{lead.case_code}</Link> : <span className="mono">{lead.case_code} <span className="muted small">(solo metadatos)</span></span>) : "—"}</dd>
          </dl>
        </div>
        <div className="card stack">
          <h2 style={{ margin: 0 }}>Siguiente paso</h2>
          {lead.allowed_transitions.length === 0 ? (
            <p className="muted">{lead.status === "convertido" ? "Lead convertido: el trabajo continúa en su expediente." : "Su perfil no puede cambiar el estado de este lead."}</p>
          ) : (
            <>
              <label className="field">Nota {reopening || pending ? "(obligatoria)" : "(opcional)"}
                <textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} placeholder={reopening ? "Por qué se reabre" : "Qué se ha hablado, por qué se descarta…"} />
              </label>
              <div className="row">{lead.allowed_transitions.map((t) => (
                <button key={t} className={`btn ${t === "descartado" || t === "no_convertido" ? "" : "btn-primary"}`} onClick={() => go(t)}>
                  {reopening && t === "contactado" ? "Reabrir" : label(ACCION_LEAD, t)}
                </button>))}</div>
              <p className="small muted">La cita pagada llegará con el módulo de Citas. Para convertir el lead, abra su expediente.</p>
            </>
          )}
        </div>
      </div>

      <div className="card">
        <h2>Historial</h2>
        <table className="data">
          <thead><tr><th>Fecha (Madrid)</th><th>Usuario</th><th>Cambio</th><th>Nota</th></tr></thead>
          <tbody>{lead.events.map((e, i) => (
            <tr key={i}><td>{fmtDateTime(e.occurred_at)}</td><td className="mono">{e.actor}</td>
              <td>{e.from_status ? `${label(LEAD_ESTADOS, e.from_status)} → ` : ""}<strong>{label(LEAD_ESTADOS, e.to_status)}</strong></td><td>{e.note ?? ""}</td></tr>
          ))}</tbody>
        </table>
      </div>
    </div>
  );
}

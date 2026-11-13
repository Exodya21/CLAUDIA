"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ProcStatusBadge, StageBadge, type Procedure } from "@/components/immigration";
import { OfficeProfile } from "@/components/immigration_form";
import { api, ApiError } from "@/lib/api";
import { FAMILIAS_EXT, FASES_EXT, fmtDate, fmtDateTime, label } from "@/lib/format";

interface InboxRow {
  case_id: string; code: string; client: string; procedure: string; stage: string; stage_label: string;
  days_in_stage: number; days_inactive: number; pending_review: number; first_expiry: string | null; expiry_alert: boolean;
}
interface Inbox { stages: Record<string, string>; counts: Record<string, number>; cases: InboxRow[] }
interface Catalog {
  procedures: Procedure[]; doc_types: Record<string, string>; can_approve: boolean;
  mercurio: { max_mb: number; formats: string[]; source: string };
}

type Tab = "bandeja" | "catalogo" | "despacho";

export default function Extranjeria() {
  const [tab, setTab] = useState<Tab>("bandeja");
  return (
    <div className="stack">
      <div className="topline">
        <div>
          <h1>Extranjería</h1>
          <p className="subtitle">Trámites desde la consulta hasta la resolución: documentación leída y confirmada, avisos de caducidad y paquete preparado para Mercurio.</p>
        </div>
      </div>
      <div className="notice notice-info small">
        <strong>Sin presentación automática</strong>
        El sistema no presenta nada en Mercurio ni descarga notificaciones de DEHú por sí mismo: prepara el paquete y los datos; el profesional presenta con su certificado y registra el resguardo.
      </div>
      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === "bandeja"} onClick={() => setTab("bandeja")}>Bandeja de trámites</button>
        <button role="tab" aria-selected={tab === "catalogo"} onClick={() => setTab("catalogo")}>Catálogo de trámites</button>
        <button role="tab" aria-selected={tab === "despacho"} onClick={() => setTab("despacho")}>Datos del despacho</button>
      </div>
      {tab === "bandeja" && <Bandeja />}
      {tab === "catalogo" && <Catalogo />}
      {tab === "despacho" && <OfficeProfile />}
    </div>
  );
}

function Bandeja() {
  const [stage, setStage] = useState("");
  const [d, setD] = useState<Inbox | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    api<Inbox>(`/immigration/inbox${stage ? `?stage=${stage}` : ""}`).then(setD).catch((e) => setErr(e instanceof ApiError ? e.message : "Error"));
  }, [stage]);
  if (err) return <div className="notice notice-danger">{err}</div>;
  if (!d) return <p className="muted">Cargando…</p>;
  const total = Object.values(d.counts).reduce((a, b) => a + b, 0);
  return (
    <div className="stack">
      <div className="chips" aria-label="Filtrar por fase">
        <button className={`btn btn-sm ${stage === "" ? "btn-primary" : ""}`} onClick={() => setStage("")}>Todas ({total})</button>
        {Object.keys(d.stages).filter((s) => d.counts[s]).map((s) => (
          <button key={s} className={`btn btn-sm ${stage === s ? "btn-primary" : ""}`} onClick={() => setStage(s)}>{label(FASES_EXT, s)} ({d.counts[s]})</button>))}
      </div>
      {d.cases.length === 0 ? <p className="muted">No hay trámites de extranjería visibles para usted{stage ? " en esta fase" : ""}.</p> : (
        <div className="table-wrap"><table className="data">
          <thead><tr><th>Expediente</th><th>Cliente</th><th>Trámite</th><th>Fase</th><th>En la fase</th><th>Por revisar</th><th>Caducidad más próxima</th></tr></thead>
          <tbody>{d.cases.map((r) => (
            <tr key={r.case_id}>
              <td><Link className="mono" href={`/expedientes/${r.case_id}`}>{r.code}</Link></td>
              <td>{r.client}</td><td className="small">{r.procedure}</td><td><StageBadge stage={r.stage} /></td>
              <td>{r.days_in_stage} días{r.days_inactive >= 15 && <div className="small error-text">Sin actividad {r.days_inactive} días</div>}</td>
              <td>{r.pending_review ? <span className="badge badge-yellow">{r.pending_review}</span> : "—"}</td>
              <td>{r.first_expiry ? <span className={r.expiry_alert ? "badge badge-red" : ""}>{fmtDate(r.first_expiry)}</span> : "—"}</td>
            </tr>))}</tbody>
        </table></div>
      )}
    </div>
  );
}

function Catalogo() {
  const [d, setD] = useState<Catalog | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const load = useCallback(() => { api<Catalog>("/immigration/procedures").then(setD).catch(() => undefined); }, []);
  useEffect(() => { load(); }, [load]);
  if (!d) return <p className="muted">Cargando…</p>;
  async function approve(p: Procedure) {
    setMsg(null);
    try {
      await api(`/immigration/procedures/${p.id}/approve`, { method: "POST", body: JSON.stringify({ note: `Revisada con ${p.sheet}` }) });
      setMsg({ ok: true, text: `«${p.name}» validada. Queda registrado quién y cuándo.` }); load();
    } catch (e) { setMsg({ ok: false, text: e instanceof ApiError ? e.message : "Error" }); }
  }
  const pending = d.procedures.filter((p) => p.status !== "aprobado").length;
  return (
    <div className="stack">
      <p className="small muted" style={{ margin: 0 }}>Cada trámite reproduce la hoja informativa oficial con su fecha. Si cambia la hoja, se crea una versión nueva pendiente de validar y los expedientes abiertos conservan la suya. Mercurio admite archivos {d.mercurio.formats.join(", ")} de hasta {d.mercurio.max_mb} MB.</p>
      {pending > 0 && <div className="notice notice-warn small">{pending} trámites pendientes de validar por Legal Extranjería.</div>}
      {msg && <div className={`notice ${msg.ok ? "notice-ok" : "notice-danger"}`}>{msg.text}</div>}
      <div className="table-wrap"><table className="data">
        <thead><tr><th>Trámite</th><th>Familia</th><th>Modelo</th><th>Mercurio</th><th>Lista</th><th></th></tr></thead>
        <tbody>{d.procedures.map((p) => (
          <ProcRow key={p.id} p={p} d={d} open={open === p.id} onToggle={() => setOpen(open === p.id ? null : p.id)} onApprove={() => approve(p)} />))}</tbody>
      </table></div>
    </div>
  );
}

function ProcRow({ p, d, open, onToggle, onApprove }: { p: Procedure; d: Catalog; open: boolean; onToggle: () => void; onApprove: () => void }) {
  return (
    <>
      <tr>
        <td><button className="link" onClick={onToggle}>{p.name}</button><div className="small muted">v{p.version} · {p.sheet}</div></td>
        <td className="small">{label(FAMILIAS_EXT, p.family)}</td><td className="small">{p.ex_form ?? "—"}</td>
        <td className="small">{p.mercurio ? "Sí" : "No"}</td>
        <td><ProcStatusBadge status={p.status} />{p.approved_by && <div className="small muted">{p.approved_by} · {fmtDateTime(p.approved_at)}</div>}</td>
        <td>{d.can_approve && p.status !== "aprobado" && <button className="btn btn-sm" onClick={onApprove}>Validar lista</button>}</td>
      </tr>
      {open && (
        <tr><td colSpan={6}>
          <dl className="kv small">
            <dt>Fuente</dt><dd><a href={p.source_url} target="_blank" rel="noreferrer">{p.source_url}</a>{p.source_updated && ` (actualizada ${p.source_updated})`}</dd>
            <dt>Base legal</dt><dd>{p.legal_basis}</dd>
            {p.fee && <><dt>Tasa</dt><dd>{p.fee}</dd></>}
            {p.window && <><dt>Cuándo</dt><dd>{p.window}</dd></>}
            {p.resolution && <><dt>Resolución</dt><dd>{p.resolution}{p.silence ? ` · silencio ${p.silence}` : ""}</dd></>}
            {p.note && <><dt>Nota</dt><dd>{p.note}</dd></>}
          </dl>
          <ul className="small">{p.requirements.map((r, i) => <li key={i}><strong>{r.label}</strong> ({r.kind}){r.note ? ` — ${r.note}` : ""} <span className="muted">[{label(d.doc_types, r.doc_type)}]</span></li>)}</ul>
        </td></tr>
      )}
    </>
  );
}

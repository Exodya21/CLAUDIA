"use client";

// F4.1 — Expediente de extranjería dentro de la ficha del expediente: trámite, fases, documentos leídos,
// lista de requisitos y paquete para Mercurio. Todo sale de la API; nada se presenta automáticamente.

import Link from "next/link";
import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import { CSRF_HEADER, api, ApiError, parseError } from "@/lib/api";
import { FormCard } from "./immigration_form";
import { DOC_ESTADOS, ESTADO_REQUISITO, FASES_EXT, fmtDate, fmtDateTime, label } from "@/lib/format";

export interface Requirement { doc_type: string; label: string; kind: string; note: string | null }
export interface Procedure {
  id: string; code: string; version: number; name: string; family: string; materia: string; status: string;
  approved_by: string | null; approved_at: string | null; sheet: string; source_url: string; source_updated: string | null;
  legal_basis: string; ex_form: string | null; fee: string | null; mercurio: boolean; resolution: string | null;
  silence: string | null; window: string | null; note: string | null; requirements: Requirement[];
}
interface Mrz { valid: boolean; surname: string; given_names: string; document_number: string; nationality: string; birth_date: string | null; expiry_date: string | null; sex: string }
interface Doc {
  id: string; status: string; doc_type: string | null; suggested_type: string | null; suggested_confidence: string | null;
  label: string | null; original_name: string; mime: string; size_bytes: number; issued_on: string | null; expires_on: string | null;
  review_note: string | null; uploaded_by: string; uploaded_at: string; reviewed_by: string | null; in_package: boolean;
  version: number; mrz: Mrz | null; warnings: string[]; ocr_engine: string | null;
  extracted?: { ficha?: Record<string, string>; info?: Record<string, string> };
}

// F4.3 — etiquetas de lo que la lectura propone para la ficha del formulario
const ROLE_LBL: Record<string, string> = { ext: "Extranjero/a", emp: "Empresa", con: "Contrato", fam: "Familiar", rep: "Representante" };
const FIELD_LBL: Record<string, string> = {
  nie: "N.I.E.", pasaporte: "Pasaporte", nombre: "Nombre", apellido1: "Primer apellido", apellido2: "Segundo apellido", sexo: "Sexo",
  fecha_nacimiento: "Nacimiento", nacionalidad: "Nacionalidad", doc: "NIF/CIF", tipo_via: "Tipo de vía", domicilio: "Vía", numero: "Número",
  piso: "Piso", letra: "Letra", escalera: "Escalera", cp: "C.P.", municipio: "Municipio", localidad: "Localidad", provincia: "Provincia",
  ccc: "Cuenta de cotización", actividad: "Actividad", cnae: "CNAE", telefono: "Teléfono", puesto: "Puesto", contrato_codigo: "Código de contrato",
  contrato_nombre: "Tipo de contrato", retribucion: "Retribución", rl_nombre: "Representante legal", rl_doc: "DNI/NIE del representante",
  rl_titulo: "Título del representante", centro_domicilio: "Centro: vía", centro_numero: "Centro: número", centro_localidad: "Centro: localidad",
  centro_cp: "Centro: C.P.", centro_provincia: "Centro: provincia", centro_piso: "Centro: piso",
};
const INFO_LBL: Record<string, string> = { nrc: "NRC del pago", importe: "Importe", codigo: "Código de tasa", dias_cotizados: "Días cotizados", alta: "Alta actual" };
const keyLabel = (k: string) => { const [r, f] = k.split("."); return `${ROLE_LBL[r] ?? r} · ${FIELD_LBL[f] ?? f}`; };
const ROLE_ORDER = Object.keys(ROLE_LBL), FIELD_ORDER = Object.keys(FIELD_LBL);
const keyRank = (k: string) => { const [r, f] = k.split("."); return ROLE_ORDER.indexOf(r) * 1000 + (FIELD_ORDER.indexOf(f) + 1 || 999); };
interface CheckItem extends Requirement { index: number; state: string; documents: string[] }
interface ImmigDetail {
  configured: true; case_id: string; code: string; materia: string; stage: string; stage_label: string; stage_since: string;
  days_in_stage: number; province: string | null; mercurio_identifier: string | null; registry_number: string | null;
  presented_at: string | null; office_file_number: string | null; resolution_at: string | null; version: number;
  procedure: Procedure; client: { name: string; nationality: string | null; birth_date: string | null };
  documents: Doc[]; checklist: CheckItem[]; alerts: { level: string; text: string; document_id?: string }[];
  next_stages: string[]; all_next: string[];
  events: { from: string | null; to: string; note: string | null; data: Record<string, unknown> | null; actor: string; at: string }[];
  can: { upload: boolean; review: boolean; package: boolean; edit: boolean };
}
interface ImmigSetup { configured: false; options: { code: string; name: string; family: string; status: string }[]; can: { edit: boolean } }
interface Catalog { doc_types: Record<string, string>; stages: Record<string, string> }

const LEGAL = new Set(["resolucion_favorable", "resolucion_desfavorable", "recurso", "cerrado"]);
const NEEDS_NOTE = new Set(["requerimiento", "recurso", "cerrado", "resolucion_desfavorable"]);
const NEEDS_DATE = new Set(["resolucion_favorable", "resolucion_desfavorable"]);
const DATE_LABEL: Record<string, string> = { presentado: "Fecha de presentación", requerimiento: "Fecha de notificación", resolucion_favorable: "Fecha de la resolución", resolucion_desfavorable: "Fecha de la resolución" };

type Msg = { ok: boolean; text: string } | null;

function kb(n: number) { return n > 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`; }

export function StageBadge({ stage }: { stage: string }) {
  const cls = stage === "resolucion_favorable" || stage === "tie" ? "badge-green" : stage === "requerimiento" || stage === "resolucion_desfavorable" || stage === "recurso" ? "badge-red" : stage === "presentado" || stage === "requerimiento_respondido" ? "badge-blue" : "badge-yellow";
  return <span className={`badge ${cls}`}>{label(FASES_EXT, stage)}</span>;
}

export function ProcStatusBadge({ status }: { status: string }) {
  return status === "aprobado" ? <span className="badge badge-green">Lista validada por Legal</span> : <span className="badge badge-yellow">Lista pendiente de validar</span>;
}

export function CaseImmigration({ caseId, onChange }: { caseId: string; onChange?: () => void }) {
  const [d, setD] = useState<ImmigDetail | ImmigSetup | null>(null);
  const [cat, setCat] = useState<Catalog | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<Msg>(null);
  const load = useCallback(() => {
    api<ImmigDetail | ImmigSetup>(`/immigration/cases/${caseId}`).then(setD).catch((e) => setErr(e instanceof ApiError ? e.message : "No disponible"));
  }, [caseId]);
  useEffect(() => { load(); api<Catalog>("/immigration/procedures").then(setCat).catch(() => undefined); }, [load]);
  if (err) return <div className="card"><h2>Extranjería</h2><div className="notice notice-warn">{err}</div></div>;
  if (!d || !cat) return <div className="card"><h2>Extranjería</h2><p className="muted">Cargando…</p></div>;
  if (!d.configured) return <Setup caseId={caseId} s={d} onDone={(x) => { setD(x); setMsg({ ok: true, text: "Trámite asignado. Ya puede subir la documentación." }); }} />;
  // Avisa a la ficha para que recargue tareas e historial (p. ej. la tarea creada por un requerimiento).
  const set = (x: ImmigDetail, m?: Msg) => { setD(x); if (m !== undefined) setMsg(m); onChange?.(); };
  return (
    <section className="stack" aria-label="Extranjería">
      <div className="card stack">
        <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <h2 style={{ margin: 0 }}>Extranjería · {d.procedure.name}</h2>
            <p className="small muted" style={{ margin: "4px 0 0" }}>
              {d.procedure.ex_form && <>Modelo {d.procedure.ex_form} · </>}{d.procedure.fee && <>Tasa: {d.procedure.fee} · </>}
              <a href={d.procedure.source_url} target="_blank" rel="noreferrer">{d.procedure.sheet}</a>
              {d.procedure.source_updated && <> (actualizada {d.procedure.source_updated})</>}
            </p>
          </div>
          <div className="row"><StageBadge stage={d.stage} /><ProcStatusBadge status={d.procedure.status} /></div>
        </div>
        {msg && <div className={`notice ${msg.ok ? "notice-ok" : "notice-danger"}`} role="status">{msg.text}</div>}
        {d.alerts.length > 0 && (
          <div className="notice notice-warn" role="alert" aria-label="Avisos del expediente">
            <strong>Avisos ({d.alerts.length})</strong>
            <ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>{d.alerts.map((a, i) => <li key={i}>{a.text}</li>)}</ul>
          </div>
        )}
        <dl className="kv">
          <dt>Fase</dt><dd>{d.stage_label} · desde {fmtDateTime(d.stage_since)} ({d.days_in_stage} días)</dd>
          <dt>Resolución prevista</dt><dd>{d.procedure.resolution ?? "—"}{d.procedure.silence ? ` · silencio ${d.procedure.silence}` : ""}</dd>
          <dt>Base legal</dt><dd className="small">{d.procedure.legal_basis}</dd>
          {d.procedure.note && <><dt>Nota de la hoja</dt><dd className="small">{d.procedure.note}</dd></>}
        </dl>
      </div>
      <div className="grid grid-2">
        <StageCard d={d} onDone={set} />
        <FilingData d={d} onDone={set} />
      </div>
      <Checklist d={d} cat={cat} />
      <Documents d={d} cat={cat} onDone={set} />
      {d.can.review && d.documents.length > 0 && <ReadingReview d={d} onDone={set} />}
      <FormCard caseId={d.case_id} docsKey={d.documents.map((x) => `${x.id}:${x.version}`).join(",")} />
      <Package d={d} />
      <div className="card">
        <h2>Historial del trámite</h2>
        <div className="table-wrap"><table className="data">
          <thead><tr><th>Fecha (Madrid)</th><th>Usuario</th><th>Cambio</th><th>Nota</th></tr></thead>
          <tbody>{d.events.map((e, i) => (
            <tr key={i}><td>{fmtDateTime(e.at)}</td><td>{e.actor}</td>
              <td>{e.from ? `${label(FASES_EXT, e.from)} → ` : ""}<strong>{label(FASES_EXT, e.to)}</strong></td>
              <td className="small">{e.note ?? ""}{e.data && "registro" in e.data && e.data.registro ? ` · Registro ${String(e.data.registro)}` : ""}{e.data && "tarea" in e.data ? " · tarea de plazo creada" : ""}</td></tr>))}</tbody>
        </table></div>
      </div>
    </section>
  );
}

function Setup({ caseId, s, onDone }: { caseId: string; s: ImmigSetup; onDone: (d: ImmigDetail) => void }) {
  const [code, setCode] = useState("");
  const [province, setProvince] = useState("");
  const [err, setErr] = useState<string | null>(null);
  async function go() {
    setErr(null);
    try { onDone(await api<ImmigDetail>(`/immigration/cases/${caseId}`, { method: "POST", body: JSON.stringify({ procedure_code: code, province: province || null }) })); }
    catch (e) { setErr(e instanceof ApiError ? e.message : "Error"); }
  }
  return (
    <div className="card stack">
      <h2 style={{ margin: 0 }}>Extranjería</h2>
      <p className="small muted" style={{ margin: 0 }}>Elija el trámite: el sistema preparará la lista de documentos de la hoja informativa oficial y las fases hasta la resolución.</p>
      {err && <div className="notice notice-danger">{err}</div>}
      {!s.can.edit ? <p className="muted">Su perfil no puede asignar el trámite.</p> : (
        <div className="form-grid">
          <label className="field">Trámite<select value={code} onChange={(e) => setCode(e.target.value)}><option value="">Elija…</option>
            {s.options.map((o) => <option key={o.code} value={o.code}>{o.name}{o.status !== "aprobado" ? " (lista pendiente de validar)" : ""}</option>)}</select></label>
          <label className="field">Provincia de presentación<input value={province} onChange={(e) => setProvince(e.target.value)} /></label>
          <div className="full"><button className="btn btn-primary btn-sm" disabled={!code} onClick={go}>Asignar trámite</button></div>
        </div>
      )}
    </div>
  );
}

function StageCard({ d, onDone }: { d: ImmigDetail; onDone: (d: ImmigDetail, m?: Msg) => void }) {
  const [to, setTo] = useState("");
  const [note, setNote] = useState("");
  const [date, setDate] = useState("");
  const [reg, setReg] = useState("");
  const [err, setErr] = useState<{ text: string; missing?: string[] } | null>(null);
  async function go() {
    setErr(null);
    try {
      const r = await api<ImmigDetail>(`/immigration/cases/${d.case_id}/stage`, { method: "POST", body: JSON.stringify({ to, note: note.trim() || null, date: date || null, registry_number: reg.trim() || null, version: d.version }) });
      onDone(r, { ok: true, text: to === "requerimiento" ? "Requerimiento registrado. Se ha creado una tarea para que el letrado fije el plazo legal con su fuente." : `Fase cambiada a «${label(FASES_EXT, to)}».` });
      setTo(""); setNote(""); setDate(""); setReg("");
    } catch (e) {
      if (e instanceof ApiError) setErr({ text: e.message, missing: (e.body.details as { missing?: string[] } | null)?.missing });
      else setErr({ text: "No se pudo cambiar la fase" });
    }
  }
  const blocked = d.all_next.filter((s) => !d.next_stages.includes(s));
  return (
    <div className="card stack">
      <h2 style={{ margin: 0 }}>Fase del trámite</h2>
      <div><StageBadge stage={d.stage} /></div>
      {d.next_stages.length === 0 ? <p className="small muted" style={{ margin: 0 }}>{d.all_next.length ? "Su perfil no puede registrar la siguiente fase: las resoluciones, recursos y cierres los registra un letrado autorizado o Dirección." : "Trámite finalizado."}</p> : (
        <>
          <label className="field">Siguiente fase<select value={to} onChange={(e) => { setTo(e.target.value); setErr(null); }}><option value="">Elija…</option>
            {d.next_stages.map((s) => <option key={s} value={s}>{label(FASES_EXT, s)}{LEGAL.has(s) ? " (efecto jurídico)" : ""}</option>)}</select></label>
          {to && DATE_LABEL[to] && <label className="field">{DATE_LABEL[to]}{NEEDS_DATE.has(to) ? " *" : ""}<input type="date" value={date} onChange={(e) => setDate(e.target.value)} /></label>}
          {to === "presentado" && <label className="field">Número de registro (resguardo)<input value={reg} onChange={(e) => setReg(e.target.value)} /></label>}
          {to && <label className="field">Nota{NEEDS_NOTE.has(to) ? " *" : ""} <span className="hint">{to === "requerimiento" ? "Qué pide la Administración" : to === "presentado" ? "Obligatoria si faltan documentos" : ""}</span>
            <textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} /></label>}
          {to === "requerimiento" && <p className="small muted" style={{ margin: 0 }}>El sistema no calcula el plazo para responder: creará una tarea para que el letrado lo proponga con su fuente y otro lo valide.</p>}
          {err && <div className="notice notice-danger">{err.text}{err.missing && <ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>{err.missing.map((m) => <li key={m}>{m}</li>)}</ul>}</div>}
          <div><button className={`btn btn-sm ${LEGAL.has(to) ? "btn-warn" : "btn-primary"}`} disabled={!to} onClick={go}>Registrar fase</button></div>
        </>
      )}
      {blocked.length > 0 && d.next_stages.length > 0 && <p className="small muted" style={{ margin: 0 }}>Reservado a letrado: {blocked.map((s) => label(FASES_EXT, s)).join(", ")}.</p>}
    </div>
  );
}

function FilingData({ d, onDone }: { d: ImmigDetail; onDone: (d: ImmigDetail, m?: Msg) => void }) {
  const [f, setF] = useState({ province: d.province ?? "", mercurio_identifier: d.mercurio_identifier ?? "", registry_number: d.registry_number ?? "", office_file_number: d.office_file_number ?? "" });
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { setF({ province: d.province ?? "", mercurio_identifier: d.mercurio_identifier ?? "", registry_number: d.registry_number ?? "", office_file_number: d.office_file_number ?? "" }); }, [d]);
  async function save() {
    setErr(null);
    try { onDone(await api<ImmigDetail>(`/immigration/cases/${d.case_id}`, { method: "PATCH", body: JSON.stringify({ ...f, version: d.version }) }), { ok: true, text: "Datos de presentación guardados." }); }
    catch (e) { setErr(e instanceof ApiError ? e.message : "Error"); }
  }
  return (
    <div className="card stack">
      <h2 style={{ margin: 0 }}>Datos de presentación</h2>
      <dl className="kv"><dt>Presentado</dt><dd>{d.presented_at ? fmtDate(d.presented_at.slice(0, 10)) : "—"}</dd><dt>Resolución</dt><dd>{d.resolution_at ? fmtDate(d.resolution_at) : "—"}</dd></dl>
      {err && <div className="notice notice-danger">{err}</div>}
      <div className="form-grid">
        <label className="field">Provincia<input disabled={!d.can.edit} value={f.province} onChange={(e) => setF({ ...f, province: e.target.value })} /></label>
        <label className="field">Identificador en Mercurio<input disabled={!d.can.edit} value={f.mercurio_identifier} onChange={(e) => setF({ ...f, mercurio_identifier: e.target.value })} /></label>
        <label className="field">Número de registro<input disabled={!d.can.edit} value={f.registry_number} onChange={(e) => setF({ ...f, registry_number: e.target.value })} /></label>
        <label className="field">Nº de expediente de la oficina<input disabled={!d.can.edit} value={f.office_file_number} onChange={(e) => setF({ ...f, office_file_number: e.target.value })} /></label>
        {d.can.edit && <div className="full"><button className="btn btn-sm" onClick={save}>Guardar datos</button></div>}
      </div>
    </div>
  );
}

function Checklist({ d, cat }: { d: ImmigDetail; cat: Catalog }) {
  const ok = d.checklist.filter((c) => c.kind === "obligatorio" && c.state === "cumplido").length;
  const total = d.checklist.filter((c) => c.kind === "obligatorio").length;
  const byId = Object.fromEntries(d.documents.map((x) => [x.id, x]));
  return (
    <div className="card">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2 style={{ margin: 0 }}>Documentación exigida</h2>
        <span className={`badge ${ok === total ? "badge-green" : "badge-yellow"}`}>{ok} de {total} obligatorios</span>
      </div>
      <p className="small muted">Según la hoja informativa oficial. {d.procedure.status !== "aprobado" && "Pendiente de validar por Legal Extranjería: compruébela antes de confiar en ella."}</p>
      <div className="table-wrap"><table className="data">
        <thead><tr><th>Documento</th><th>Tipo</th><th>Estado</th><th>Aportado</th></tr></thead>
        <tbody>{d.checklist.map((c) => (
          <tr key={c.index}><td>{c.label}{c.note && <div className="small muted">{c.note}</div>}</td>
            <td className="small">{c.kind}</td>
            <td><span className={`badge ${c.state === "cumplido" ? "badge-green" : c.state === "caducado" || (c.state === "falta" && c.kind === "obligatorio") ? "badge-red" : "badge-yellow"}`}>{label(ESTADO_REQUISITO, c.state)}</span></td>
            <td className="small">{c.documents.map((id) => byId[id]?.label || label(cat.doc_types, byId[id]?.doc_type ?? "otros")).join(", ") || "—"}</td></tr>))}</tbody>
      </table></div>
    </div>
  );
}

function Documents({ d, cat, onDone }: { d: ImmigDetail; cat: Catalog; onDone: (d: ImmigDetail, m?: Msg) => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [results, setResults] = useState<{ name: string; ok: boolean; error?: string; suggested_type?: string | null; confidence?: string | null; message?: string | null }[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  async function upload(files: FileList) {
    setBusy(true); setErr(null); setResults([]);
    const fd = new FormData();
    Array.from(files).forEach((f) => fd.append("files", f));
    const res = await fetch(`/api/v1/immigration/cases/${d.case_id}/documents`, { method: "POST", body: fd, headers: CSRF_HEADER, credentials: "same-origin" });
    const data = await res.json().catch(() => null);
    setBusy(false);
    if (input.current) input.current.value = "";
    if (!res.ok) { setErr(parseError(res.status, data).message); return; }
    setResults(data.results);
    if (data.case) onDone(data.case, { ok: true, text: "Documentos leídos. Revise y confirme cada propuesta." });
  }
  const pending = d.documents.filter((x) => x.status === "pendiente_revision");
  return (
    <div className="card stack">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2 style={{ margin: 0 }}>Documentos del cliente</h2>
        {pending.length > 0 && <span className="badge badge-yellow">{pending.length} por revisar</span>}
      </div>
      {d.can.upload && (
        <div className="stack" style={{ gap: 6 }}>
          <label className="field">Subir documentos (PDF, JPG o PNG; varios a la vez)
            <input ref={input} type="file" multiple accept="application/pdf,image/jpeg,image/png" disabled={busy} onChange={(e) => e.target.files?.length && upload(e.target.files)} /></label>
          <p className="small muted" style={{ margin: 0 }}>El servidor lee cada archivo (incluida la zona MRZ de pasaportes y TIE) y propone tipo y fechas. Nada se da por bueno hasta que una persona lo confirma.</p>
          {busy && <p className="small">Leyendo documentos…</p>}
          {err && <div className="notice notice-danger">{err}</div>}
          {results.length > 0 && <ul className="small" style={{ margin: 0, paddingLeft: 18 }}>{results.map((r, i) => <li key={i}>{r.name}: {r.ok ? `${r.suggested_type ? `parece ${label(cat.doc_types, r.suggested_type)} (confianza ${r.confidence})` : "tipo no reconocido"}${r.message ? ` — ${r.message}` : ""}` : <span className="error-text">{r.error}</span>}</li>)}</ul>}
        </div>
      )}
      {d.documents.length === 0 ? <p className="muted">Aún no hay documentos.</p> : (
        <div className="table-wrap"><table className="data">
          <thead><tr><th>Documento</th><th>Lectura</th><th>Validez</th><th>Estado</th><th></th></tr></thead>
          <tbody>{d.documents.map((x) => (
            <DocRow key={x.id} x={x} d={d} cat={cat} open={open === x.id} onToggle={() => setOpen(open === x.id ? null : x.id)} onDone={(r, m) => { setOpen(null); onDone(r, m); }} />))}</tbody>
        </table></div>
      )}
    </div>
  );
}

function ReadData({ x }: { x: Doc }) {
  const ficha = Object.entries(x.extracted?.ficha ?? {}).sort(([a], [b]) => keyRank(a) - keyRank(b));
  const info = Object.entries(x.extracted?.info ?? {});
  if (!ficha.length && !info.length) return null;
  return (
    <details aria-label={`Datos leídos de ${x.label || x.original_name}`}>
      <summary>{ficha.length ? `${ficha.length} datos leídos para la ficha` : "Datos leídos"}{x.status !== "valido" && ficha.length ? " (pasan a la ficha al marcarlo válido)" : ""}</summary>
      <dl className="small" style={{ display: "grid", gridTemplateColumns: "max-content 1fr", gap: "2px 10px", margin: "6px 0" }}>
        {[...ficha.map(([k, v]) => [keyLabel(k), v]), ...info.map(([k, v]) => [INFO_LBL[k] ?? k, v])].map(([k, v]) => <Fragment key={k}><dt className="muted">{k}</dt><dd style={{ margin: 0 }}>{v}</dd></Fragment>)}
      </dl>
    </details>
  );
}

function DocRow({ x, d, cat, open, onToggle, onDone }: { x: Doc; d: ImmigDetail; cat: Catalog; open: boolean; onToggle: () => void; onDone: (d: ImmigDetail, m?: Msg) => void }) {
  return (
    <>
      <tr>
        <td><a href={`/api/v1/immigration/documents/${x.id}/file`} target="_blank" rel="noreferrer">{x.label || x.original_name}</a>
          <div className="small muted">{x.original_name} · {kb(x.size_bytes)} · {x.uploaded_by}</div></td>
        <td className="small">{x.suggested_type ? <>Parece <strong>{label(cat.doc_types, x.suggested_type)}</strong> ({x.suggested_confidence})</> : "Sin propuesta"}
          {x.mrz && <div>MRZ {x.mrz.valid ? "correcta" : "con errores"}: {x.mrz.surname}, {x.mrz.given_names} · {x.mrz.document_number} · {x.mrz.nationality}</div>}
          <ReadData x={x} /></td>
        <td className="small">{x.expires_on ? `Caduca ${fmtDate(x.expires_on)}` : x.issued_on ? `Expedido ${fmtDate(x.issued_on)}` : "—"}
          {x.warnings.filter((w) => !w.startsWith("Pendiente")).map((w) => <div key={w} className="error-text">{w}</div>)}</td>
        <td><span className={`badge ${x.status === "valido" ? "badge-green" : x.status === "rechazado" ? "badge-red" : "badge-yellow"}`}>{label(DOC_ESTADOS, x.status)}</span>
          {x.doc_type && <div className="small">{label(cat.doc_types, x.doc_type)}</div>}</td>
        <td>{d.can.review && <button className="btn btn-sm" onClick={onToggle}>{open ? "Cerrar" : x.status === "pendiente_revision" ? "Revisar" : "Corregir"}</button>}</td>
      </tr>
      {open && <tr><td colSpan={5}><ReviewForm x={x} cat={cat} onDone={onDone} /><DocTools x={x} onDone={onDone} /></td></tr>}
    </>
  );
}

// F4.3 — revisión automática: el sistema dice qué ha fallado en la lectura de cada documento (sin datos)
interface ReviewItem { id: string; nombre: string; tipo: string; estado: string; paginas: number | null; leidos: string[]; problemas: { level: string; text: string }[]; antiguo: boolean }
interface ReviewOut { documentos: ReviewItem[]; ficha_vacia: { apartado: string; campos: string[] }[]; contradicciones: string[]; antiguos: string[]; informe: string }
const LEVEL: Record<string, string> = { error: "badge-red", aviso: "badge-yellow", accion: "badge-yellow", info: "badge-blue" };
const LEVEL_TXT: Record<string, string> = { error: "Error", aviso: "Revisar", accion: "Acción", info: "Info" };

function ReadingReview({ d, onDone }: { d: ImmigDetail; onDone: (d: ImmigDetail, m?: Msg) => void }) {
  const [r, setR] = useState<ReviewOut | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const key = d.documents.map((x) => `${x.id}:${x.version}`).join(",");
  useEffect(() => {
    api<ReviewOut>(`/immigration/cases/${d.case_id}/reading-review`).then(setR).catch(() => setR(null));
  }, [d.case_id, key]);
  if (!r) return null;
  const withProblems = r.documentos.filter((x) => x.problemas.some((p) => p.level !== "info"));
  async function rereadOld() {
    let last: ImmigDetail | null = null;
    for (const [i, id] of r!.antiguos.entries()) {
      setBusy(`Leyendo ${i + 1} de ${r!.antiguos.length}… (un pasaporte completo puede tardar 1 minuto)`);
      try { last = await api<ImmigDetail>(`/immigration/documents/${id}/reread`, { method: "POST" }); } catch { /* sigue con el resto */ }
    }
    setBusy(null);
    if (last) onDone(last, { ok: true, text: "Documentos leídos de nuevo con la versión actual." });
  }
  async function copy() {
    try { await navigator.clipboard.writeText(r!.informe); setMsg("Informe copiado. Péguelo en el chat con Claude."); }
    catch { setMsg("No se pudo copiar: selecciónelo abajo y cópielo a mano."); }
  }
  return (
    <div className="card stack" aria-label="Revisión automática de la lectura">
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={{ margin: 0 }}>Revisión automática de la lectura</h2>
        <div className="row" style={{ gap: 8 }}>
          {r.antiguos.length > 0 && <button className="btn btn-sm btn-primary" disabled={!!busy} onClick={rereadOld}>Volver a leer {r.antiguos.length} documento(s) antiguo(s)</button>}
          <button className="btn btn-sm" onClick={copy}>Copiar informe para Claude (sin datos)</button>
        </div>
      </div>
      {busy && <div className="notice notice-info small" role="status">{busy}</div>}
      {msg && <div className="notice notice-info small" role="status">{msg}</div>}
      <p className="small muted" style={{ margin: 0 }}>El sistema comprueba solo lo que ha leído de cada documento y le dice qué falta o qué ha descartado. El informe para Claude no lleva nombres, números ni direcciones.</p>
      {withProblems.length === 0 && r.ficha_vacia.length === 0 && r.contradicciones.length === 0
        ? <div className="notice notice-ok small">Sin problemas de lectura detectados.</div>
        : <ul className="stack" style={{ gap: 8, margin: 0, paddingLeft: 0, listStyle: "none" }}>
          {r.documentos.filter((x) => x.problemas.length).map((x) => (
            <li key={x.id} className="small" aria-label={`Lectura de ${x.tipo}`}>
              <strong>{x.tipo}</strong> <span className="muted">· {x.estado === "valido" ? "válido" : x.estado === "pendiente_revision" ? "por revisar" : x.estado}{x.paginas ? ` · ${x.paginas} pág.` : ""} · {x.leidos.length} datos leídos</span>
              <ul style={{ margin: "2px 0 0", paddingLeft: 18 }}>
                {x.problemas.map((p, i) => <li key={i}><span className={`badge ${LEVEL[p.level] ?? ""}`}>{LEVEL_TXT[p.level] ?? p.level}</span> {p.text}</li>)}
              </ul>
            </li>))}
          {r.ficha_vacia.map((e) => <li key={e.apartado} className="small"><span className="badge badge-yellow">Ficha</span> <strong>{e.apartado}</strong>: sin dato ni propuesta en {e.campos.join(", ")}.</li>)}
          {r.contradicciones.length > 0 && <li className="small"><span className="badge badge-yellow">Ficha</span> Los documentos no coinciden en: {r.contradicciones.join(", ")}.</li>}
        </ul>}
      <details><summary className="small">Ver el informe que se copia</summary>
        <textarea readOnly value={r.informe} rows={12} aria-label="Informe de lectura sin datos" style={{ fontFamily: "monospace", fontSize: 12, width: "100%" }} />
      </details>
    </div>
  );
}

// F4.3 — volver a leer con la lectura actual y diagnóstico de la lectura SIN datos (para mejorar formatos)
function DocTools({ x, onDone }: { x: Doc; onDone: (d: ImmigDetail, m?: Msg) => void }) {
  const [busy, setBusy] = useState(false);
  const [diag, setDiag] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  async function reread() {
    setBusy(true); setMsg(null);
    try {
      const r = await api<ImmigDetail>(`/immigration/documents/${x.id}/reread`, { method: "POST" });
      onDone(r, { ok: true, text: "Documento leído de nuevo. Revise los datos leídos." });
    } catch (e) { setMsg(e instanceof ApiError ? e.message : "No se pudo leer"); } finally { setBusy(false); }
  }
  async function diagnostic() {
    setMsg(null);
    try { setDiag(JSON.stringify(await api(`/immigration/documents/${x.id}/diagnostic`), null, 1)); }
    catch (e) { setMsg(e instanceof ApiError ? e.message : "No disponible"); }
  }
  async function copy() {
    try { await navigator.clipboard.writeText(diag ?? ""); setMsg("Copiado."); } catch { setMsg("Selecciónelo y cópielo a mano."); }
  }
  return (
    <div className="stack" style={{ gap: 6, marginTop: 10, borderTop: "1px solid var(--line)", paddingTop: 10 }} aria-label={`Herramientas de lectura de ${x.original_name}`}>
      <div className="row" style={{ gap: 8 }}>
        <button className="btn btn-sm" disabled={busy} onClick={reread}>{busy ? "Leyendo… (un pasaporte completo puede tardar 1 minuto)" : "Volver a leer"}</button>
        <button className="btn btn-sm" onClick={diagnostic}>Diagnóstico de la lectura (sin datos)</button>
        {msg && <span className="small muted" role="status">{msg}</span>}
      </div>
      {diag && <>
        <p className="small muted" style={{ margin: 0 }}>Solo se ven las palabras del formulario; nombres, números y direcciones salen como XXX y 999. Revíselo antes de enviarlo.</p>
        <textarea readOnly value={diag} rows={10} aria-label="Diagnóstico sin datos" style={{ fontFamily: "monospace", fontSize: 12 }} />
        <div><button className="btn btn-sm" onClick={copy}>Copiar diagnóstico</button></div>
      </>}
    </div>
  );
}

function ReviewForm({ x, cat, onDone }: { x: Doc; cat: Catalog; onDone: (d: ImmigDetail, m?: Msg) => void }) {
  const [f, setF] = useState({ doc_type: x.doc_type ?? x.suggested_type ?? "", label: x.label ?? "", issued_on: x.issued_on ?? "", expires_on: x.expires_on ?? "", in_package: x.in_package, note: "" });
  const [retire, setRetire] = useState("");
  const [err, setErr] = useState<string | null>(null);
  async function save(status: "valido" | "rechazado") {
    setErr(null);
    try {
      const r = await api<ImmigDetail>(`/immigration/documents/${x.id}/review`, { method: "POST", body: JSON.stringify({ ...f, status, issued_on: f.issued_on || null, expires_on: f.expires_on || null, label: f.label || null, note: f.note || null, version: x.version }) });
      onDone(r, { ok: true, text: status === "valido" ? "Documento confirmado." : "Documento marcado como no válido." });
    } catch (e) { setErr(e instanceof ApiError ? e.message : "Error"); }
  }
  async function doRetire() {
    setErr(null);
    try { onDone(await api<ImmigDetail>(`/immigration/documents/${x.id}/retire`, { method: "POST", body: JSON.stringify({ reason: retire }) }), { ok: true, text: "Documento retirado del expediente (se conserva en el historial)." }); }
    catch (e) { setErr(e instanceof ApiError ? e.message : "Error"); }
  }
  return (
    <div className="stack" style={{ gap: 8 }} aria-label={`Revisión de ${x.original_name}`}>
      {err && <div className="notice notice-danger">{err}</div>}
      <div className="form-grid">
        <label className="field">Tipo de documento<select value={f.doc_type} onChange={(e) => setF({ ...f, doc_type: e.target.value })}><option value="">Elija…</option>
          {Object.entries(cat.doc_types).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
        <label className="field">Nombre en el expediente<input value={f.label} onChange={(e) => setF({ ...f, label: e.target.value })} placeholder={label(cat.doc_types, f.doc_type || "otros")} /></label>
        <label className="field">Fecha de expedición<input type="date" value={f.issued_on} onChange={(e) => setF({ ...f, issued_on: e.target.value })} /></label>
        <label className="field">Fecha de caducidad<input type="date" value={f.expires_on} onChange={(e) => setF({ ...f, expires_on: e.target.value })} /></label>
        <label className="field full">Observaciones <span className="hint">Obligatorias si no es válido</span><input value={f.note} onChange={(e) => setF({ ...f, note: e.target.value })} /></label>
        <label className="row small full"><input type="checkbox" style={{ width: "auto" }} checked={f.in_package} onChange={(e) => setF({ ...f, in_package: e.target.checked })} /> Incluir en el paquete para Mercurio</label>
      </div>
      <div className="row">
        <button className="btn btn-sm btn-primary" disabled={!f.doc_type} onClick={() => save("valido")}>Confirmar como válido</button>
        <button className="btn btn-sm btn-warn" disabled={!f.doc_type} onClick={() => save("rechazado")}>No válido</button>
        <span className="spacer" />
        <input style={{ maxWidth: 260 }} aria-label="Motivo para retirar" placeholder="Motivo para retirar…" value={retire} onChange={(e) => setRetire(e.target.value)} />
        <button className="btn btn-sm" disabled={retire.trim().length < 5} onClick={doRetire}>Retirar</button>
      </div>
    </div>
  );
}

function Package({ d }: { d: ImmigDetail }) {
  const [chk, setChk] = useState<{ ready: boolean; blocking: string[]; warnings: string[]; files: { id: string; label: string; size_bytes: number; mime: string }[] } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  if (!d.can.package) return null;
  async function check() {
    setErr(null);
    try { setChk(await api(`/immigration/cases/${d.case_id}/package/check`)); } catch (e) { setErr(e instanceof ApiError ? e.message : "Error"); }
  }
  return (
    <div className="card stack">
      <h2 style={{ margin: 0 }}>Paquete para Mercurio</h2>
      <p className="small muted" style={{ margin: 0 }}>Prepara los documentos confirmados en el orden de la hoja, convertidos a formatos admitidos (PDF/JPG, máximo 6 MB por archivo), con un índice y la ficha de datos para el formulario. La presentación la hace el profesional en Mercurio con su certificado; después suba aquí el resguardo y registre la fase «Presentado».</p>
      {!d.procedure.mercurio && <div className="notice notice-info small">Según la hoja oficial, este trámite no se presenta por Mercurio.</div>}
      <div className="row"><button className="btn btn-sm" onClick={check}>Comprobar paquete</button>
        {chk?.ready && <a className="btn btn-sm btn-primary" href={`/api/v1/immigration/cases/${d.case_id}/package.zip`}>Descargar paquete (.zip)</a>}</div>
      {err && <div className="notice notice-danger">{err}</div>}
      {chk && (
        <>
          {chk.ready ? <div className="notice notice-ok">Listo: {chk.files.length} documentos.</div> : (
            <div className="notice notice-danger"><strong>No está listo para presentar</strong><ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>{chk.blocking.map((b) => <li key={b}>{b}</li>)}</ul>
              <a className="small" href={`/api/v1/immigration/cases/${d.case_id}/package.zip?force=true`}>Descargar igualmente (borrador incompleto; queda registrado)</a></div>)}
          {chk.warnings.length > 0 && <ul className="small" style={{ margin: 0, paddingLeft: 18 }}>{chk.warnings.map((w) => <li key={w}>{w}</li>)}</ul>}
          {chk.files.length > 0 && <ol className="small" style={{ margin: 0 }}>{chk.files.map((f) => <li key={f.id}>{f.label} · {kb(f.size_bytes)}</li>)}</ol>}
        </>
      )}
    </div>
  );
}

export function ExtLink({ caseId, code }: { caseId: string; code: string }) {
  return <Link href={`/expedientes/${caseId}`} className="mono">{code}</Link>;
}

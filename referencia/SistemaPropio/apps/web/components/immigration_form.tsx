"use client";

// F4.2/F4.3 — Ficha de datos del modelo EX: propuestas (cliente, pasaporte, despacho) que una persona confirma,
// borrador del PDF oficial y código temporal para la extensión que rellena Mercurio (sin presentar).

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError, fieldErrors } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";

interface SpecField { key: string; label: string; choices: Record<string, string> | null }
interface Spec {
  model: string; code: string; title: string;
  roles: { role: string; label: string; fields: SpecField[] }[];
  options: { field: string; label: string; section: string }[];
  extra_text: { field: string; label: string; section: string }[];
  pdf: boolean;
}
interface FormData {
  available: boolean; message?: string; model: string; default_model: string | null; spec: Spec;
  values: Record<string, string>; options: string[]; extra: Record<string, string>;
  proposals: Record<string, { value: string; source: string; others?: { value: string; source: string }[] }>;
  differs?: Record<string, { value: string; source: string }>; version: number | null;
  confirmed_by: string | null; confirmed_at: string | null; office_configured: boolean; procedure_model?: string;
  models: { code: string; model: string; title: string }[];
  can: { edit: boolean; pdf: boolean; token: boolean };
}

const SOURCE: Record<string, string> = { cliente: "ficha del cliente", pasaporte: "pasaporte leído", despacho: "datos del despacho", hoy: "fecha de hoy", expediente: "expediente" };
const srcLabel = (s: string) => SOURCE[s] ?? s.replace(/^documento: /, "documento leído: ");

export function FormCard({ caseId, docsKey = "" }: { caseId: string; docsKey?: string }) {
  const [d, setD] = useState<FormData | null>(null);
  const [model, setModel] = useState<string | null>(null);
  const [vals, setVals] = useState<Record<string, string>>({});
  const [opts, setOpts] = useState<string[]>([]);
  const [extra, setExtra] = useState<Record<string, string>>({});
  const [errs, setErrs] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [token, setToken] = useState<{ code: string; expires_at: string } | null>(null);
  const [open, setOpen] = useState<string>("ext");

  // Campos que la persona ha tocado y aún no ha guardado: una recarga no los pisa
  const touched = useRef<Record<string, string>>({});
  const apply = useCallback((r: FormData) => {
    setD(r);
    if (!r.available) return;
    const v: Record<string, string> = { ...r.values };
    for (const [k, p] of Object.entries(r.proposals)) if (!(k in v)) v[k] = p.value;
    setVals({ ...v, ...touched.current }); setOpts(r.options); setExtra(r.extra); setErrs({});
  }, []);
  const edit = (k: string, value: string) => { touched.current = { ...touched.current, [k]: value }; setVals((x) => ({ ...x, [k]: value })); };
  const load = useCallback((m?: string | null) => {
    api<FormData>(`/immigration/cases/${caseId}/form${m ? `?model=${m}` : ""}`).then(apply).catch((e) => setMsg({ ok: false, text: e instanceof ApiError ? e.message : "No disponible" }));
  }, [apply, caseId]);
  // se recarga al validar o corregir documentos: sus datos leídos pueden traer propuestas nuevas
  useEffect(() => { touched.current = {}; }, [model]);
  useEffect(() => { load(model); }, [load, model, docsKey]);

  const pendingCount = useMemo(() => d?.available ? Object.keys(d.proposals).filter((k) => !(k in d.values)).length : 0, [d]);
  if (!d) return <div className="card"><h2>Datos para el formulario</h2><p className="muted">Cargando…</p></div>;
  if (!d.available) {
    return (
      <div className="card stack">
        <h2 style={{ margin: 0 }}>Datos para el formulario</h2>
        <div className="notice notice-info small">{d.message}</div>
        <label className="field">Modelo<select value="" onChange={(e) => setModel(e.target.value)}><option value="">Elija…</option>
          {d.models.map((m) => <option key={m.code} value={m.code}>{m.model} · {m.title}</option>)}</select></label>
      </div>
    );
  }

  async function save() {
    setMsg(null); setErrs({});
    try {
      const r = await api<FormData>(`/immigration/cases/${caseId}/form`, { method: "PUT", body: JSON.stringify({ model: d!.model, values: vals, options: opts, extra, version: d!.version }) });
      touched.current = {}; apply(r); setToken(null);
      setMsg({ ok: true, text: "Ficha guardada. Solo estos datos confirmados se usan para rellenar Mercurio." });
    } catch (e) {
      setErrs(fieldErrors(e));
      setMsg({ ok: false, text: e instanceof ApiError ? e.message : "No se pudo guardar" });
    }
  }
  async function newToken() {
    setMsg(null);
    try { setToken(await api(`/immigration/cases/${caseId}/fill-token`, { method: "POST" })); }
    catch (e) { setMsg({ ok: false, text: e instanceof ApiError ? e.message : "Error" }); }
  }
  const prop = (k: string) => (!(k in d.values) && d.proposals[k]) ? d.proposals[k] : null;
  const dirty = JSON.stringify(vals) !== JSON.stringify(d.values) || JSON.stringify([...opts].sort()) !== JSON.stringify([...d.options].sort()) || JSON.stringify(extra) !== JSON.stringify(d.extra);
  const mainOpts = d.spec.options;
  const sections = Array.from(new Set(mainOpts.map((o) => o.section)));

  return (
    <div className="card stack" aria-label="Datos para el formulario">
      <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h2 style={{ margin: 0 }}>Datos para el formulario {d.spec.pdf ? d.spec.model : d.procedure_model ?? ""}</h2>
          <p className="small muted" style={{ margin: "4px 0 0" }}>{d.spec.pdf ? d.spec.title : "Datos comunes de las pantallas de Mercurio (no tenemos el modelo PDF de este trámite)."}</p>
        </div>
        <label className="field" style={{ minWidth: 220 }}>Modelo
          <select value={d.model} onChange={(e) => setModel(e.target.value)}>
            {d.models.map((m) => <option key={m.code} value={m.code}>{m.code === "GENERAL" ? "General (datos comunes)" : m.model}{m.code === d.default_model ? " (el del trámite)" : ""}</option>)}</select></label>
      </div>
      <p className="small muted" style={{ margin: 0 }}>
        Son los datos que Mercurio pide en sus pestañas{d.spec.pdf ? ` para el ${d.spec.model} (el modelo que Mercurio genera al final)` : ""}. Una vez guardados, la extensión los escribe en las pestañas de Mercurio; la vista previa es solo para revisar. Los campos en amarillo son <strong>propuestas</strong> (de la ficha del cliente, de los documentos ya revisados —pasaporte, TIE, contrato, padrón— o de los datos del despacho): revíselos y pulse «Guardar ficha».
        {d.confirmed_at && <> Última confirmación: {d.confirmed_by}, {fmtDateTime(d.confirmed_at)}.</>}
      </p>
      {!d.office_configured && <div className="notice notice-warn small">Faltan los datos del despacho como representante: Dirección o Líder Extranjería los introducen en Extranjería → Datos del despacho.</div>}
      {pendingCount > 0 && <div className="notice notice-info small">{pendingCount} datos propuestos pendientes de confirmar.</div>}
      {msg && <div className={`notice ${msg.ok ? "notice-ok" : "notice-danger"}`} role="status">{msg.text}</div>}

      <div className="tabs" role="tablist" aria-label="Apartados del formulario">
        {d.spec.roles.map((r) => <button key={r.role} role="tab" aria-selected={open === r.role} onClick={() => setOpen(r.role)}>{r.label.split(" (")[0]}</button>)}
        {(mainOpts.length > 0 || d.spec.extra_text.length > 0) && <button role="tab" aria-selected={open === "opts"} onClick={() => setOpen("opts")}>Tipo de solicitud</button>}
      </div>
      {d.spec.roles.filter((r) => r.role === open).map((r) => (
        <div key={r.role} className="form-grid">
          {r.fields.map((f) => {
            const p = prop(f.key);
            const style = p && vals[f.key] === p.value ? { background: "var(--warn-bg, #fff6db)" } : undefined;
            return (
              <label key={f.key} className="field">{f.label}
                {p && <span className="hint">Propuesto: {srcLabel(p.source)}</span>}
                {p?.others?.map((o) => <span key={o.source} className="hint" style={{ color: "var(--danger, #a12)" }}>Ojo: {srcLabel(o.source)} dice «{o.value}»</span>)}
                {d.differs?.[f.key] && <span className="hint" style={{ color: "var(--danger, #a12)" }}>Ojo: {srcLabel(d.differs[f.key].source)} dice «{d.differs[f.key].value}» (no se ha cambiado)</span>}
                {f.choices ? (
                  <select disabled={!d.can.edit} style={style} value={vals[f.key] ?? ""} onChange={(e) => edit(f.key, e.target.value)}>
                    <option value="">—</option>{Object.entries(f.choices).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
                ) : (
                  <input disabled={!d.can.edit} style={style} type={f.key.endsWith("fecha_nacimiento") ? "date" : "text"} value={vals[f.key] ?? ""}
                    onChange={(e) => edit(f.key, e.target.value)} aria-invalid={!!errs[f.key]} />
                )}
                {errs[f.key] && <span className="error-text">{errs[f.key]}</span>}
              </label>
            );
          })}
        </div>
      ))}
      {open === "opts" && (
        <div className="stack" style={{ gap: 6 }}>
          <p className="small muted" style={{ margin: 0 }}>Marque las casillas del modelo que correspondan. El sistema no elige el supuesto legal: lo decide el profesional.</p>
          {sections.map((sec) => (
            <fieldset key={sec} className="stack" style={{ gap: 4, border: "1px solid var(--line)", borderRadius: 8, padding: "8px 12px" }}>
              <legend className="small" style={{ fontWeight: 600 }}>{sec.replace(/\(\d+\)/g, "")}</legend>
              {mainOpts.filter((o) => o.section === sec).map((o) => (
                <label key={o.field} className="row small" style={{ alignItems: "flex-start", flexWrap: "nowrap" }}>
                  <input type="checkbox" style={{ width: "auto", marginTop: 3 }} disabled={!d.can.edit} checked={opts.includes(o.field)}
                    onChange={(e) => setOpts(e.target.checked ? [...opts, o.field] : opts.filter((x) => x !== o.field))} />
                  <span>{o.label || "(casilla sin texto)"}</span></label>))}
            </fieldset>))}
          {d.spec.extra_text.length > 0 && <div className="form-grid">{d.spec.extra_text.map((e) => (
            <label key={e.field} className="field">{e.label}<input disabled={!d.can.edit} value={extra[e.field] ?? ""} onChange={(ev) => setExtra({ ...extra, [e.field]: ev.target.value })} /></label>))}</div>}
        </div>
      )}

      <div className="row">
        {d.can.edit && <button className="btn btn-sm btn-primary" disabled={!dirty && pendingCount === 0} onClick={save}>Guardar ficha</button>}
        {d.can.pdf && d.spec.pdf && d.version && !dirty && <a className="btn btn-sm" href={`/api/v1/immigration/cases/${caseId}/form.pdf`}>Vista previa del {d.spec.model} (borrador interno)</a>}
        {d.can.token && d.version && !dirty && <button className="btn btn-sm" onClick={newToken}>Rellenar en Mercurio</button>}
        {dirty && <span className="small muted">Hay cambios sin guardar.</span>}
      </div>
      {token && (
        <div className="notice notice-ok" role="status" aria-label="Código para la extensión">
          <strong>Código para la extensión: <span className="mono" style={{ fontSize: 18, letterSpacing: 1 }}>{token.code}</span></strong>
          <ol className="small" style={{ margin: "6px 0 0", paddingLeft: 18 }}>
            <li>En Mercurio (acceso Abogacía) abra «Presentar nueva solicitud» y elija el modelo {d.spec.model}.</li>
            <li>Pulse el icono de la extensión «SISTEMA PROPIO · Mercurio», escriba el código y pulse «Traer datos».</li>
            <li>En cada pestaña de Mercurio pulse «Rellenar esta página» y revise lo que queda en verde.</li>
            <li>Usted adjunta los documentos del paquete, revisa, firma con AutoFirma y presenta. La extensión no pulsa ningún botón de Mercurio.</li>
          </ol>
          <span className="small">Caduca a las {fmtDateTime(token.expires_at)} y solo sirve para este expediente.</span>
        </div>
      )}
    </div>
  );
}

export interface Office { organization_id: string; data: Record<string, string>; version: number | null; updated_at: string | null; labels: Record<string, string>; can_edit: boolean }

export function OfficeProfile() {
  const [offices, setOffices] = useState<Office[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const load = useCallback(() => { api<{ offices: Office[] }>("/immigration/office").then((r) => setOffices(r.offices)).catch((e) => setErr(e instanceof ApiError ? e.message : "Error")); }, []);
  useEffect(() => { load(); }, [load]);
  if (err) return <div className="notice notice-warn">{err}</div>;
  if (!offices) return <p className="muted">Cargando…</p>;
  return <div className="stack">{offices.map((o) => <OfficeForm key={o.organization_id} o={o} onSaved={load} />)}</div>;
}

function OfficeForm({ o, onSaved }: { o: Office; onSaved: () => void }) {
  const [f, setF] = useState<Record<string, string>>(o.data);
  const [errs, setErrs] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  async function save() {
    setMsg(null); setErrs({});
    try { await api(`/immigration/office/${o.organization_id}`, { method: "PUT", body: JSON.stringify({ data: f, version: o.version }) }); setMsg({ ok: true, text: "Datos del despacho guardados." }); onSaved(); }
    catch (e) { setErrs(fieldErrors(e)); setMsg({ ok: false, text: e instanceof ApiError ? e.message : "Error" }); }
  }
  return (
    <div className="card stack">
      <p className="small muted" style={{ margin: 0 }}>Se proponen en el apartado «Representante a efectos de presentación» de todos los modelos EX y, si no indica otro, como domicilio de notificaciones. {o.updated_at && `Actualizado ${fmtDateTime(o.updated_at)}.`}</p>
      {msg && <div className={`notice ${msg.ok ? "notice-ok" : "notice-danger"}`}>{msg.text}</div>}
      <div className="form-grid">
        {Object.entries(o.labels).map(([k, l]) => (
          <label key={k} className="field">{l}<input disabled={!o.can_edit} value={f[k] ?? ""} onChange={(e) => setF({ ...f, [k]: e.target.value })} aria-invalid={!!errs[k]} />
            {errs[k] && <span className="error-text">{errs[k]}</span>}</label>))}
      </div>
      {o.can_edit ? <div><button className="btn btn-sm btn-primary" onClick={save}>Guardar datos del despacho</button></div> : <p className="small muted" style={{ margin: 0 }}>Solo Dirección o Líder Extranjería pueden cambiarlos.</p>}
    </div>
  );
}

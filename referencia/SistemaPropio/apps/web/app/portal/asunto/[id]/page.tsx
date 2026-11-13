"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, CSRF_HEADER, parseError } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";
import { isAuthError, papi, type PortalMsg, type PortalThread } from "@/lib/portal";

async function sendForm(path: string, f: FormData): Promise<PortalThread> {
  const res = await fetch(`/api/v1/portal${path}`, { method: "POST", body: f, headers: CSRF_HEADER, credentials: "same-origin" });
  const data = await res.json().catch(() => null);
  if (!res.ok) throw parseError(res.status, data);
  return data as PortalThread;
}

export default function Asunto() {
  const { id } = useParams<{ id: string }>();
  const [t, setT] = useState<PortalThread | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const writing = useRef(false);
  const box = useRef<HTMLDivElement>(null);
  const count = t?.messages.length ?? 0;
  useEffect(() => { if (box.current) box.current.scrollTop = box.current.scrollHeight; }, [count]);
  const load = useCallback(() => papi<PortalThread>(`/threads/${id}`).then((r) => { setT(r); setErr(null); }).catch((e) => {
    if (isAuthError(e)) { window.location.href = "/portal"; return; }
    setErr(e instanceof ApiError ? e.message : "No se ha podido cargar.");
  }), [id]);
  useEffect(() => { load(); const i = setInterval(() => { if (!writing.current) load(); }, 20000); return () => clearInterval(i); }, [load]);
  if (err) return <div className="stack"><div className="notice notice-danger" role="alert">{err}</div><Link href="/portal">Volver a sus asuntos</Link></div>;
  if (!t) return <p className="muted">Cargando…</p>;
  const urgent = t.messages.filter((m) => m.requires_confirmation && !m.confirmed_at);
  return (
    <div className="stack">
      <p className="small" style={{ margin: 0 }}><Link href="/portal">← Sus asuntos</Link></p>
      <div>
        <h1 style={{ margin: 0 }}>{t.case ? `${t.case.materia}${t.case.procedure ? ` · ${t.case.procedure}` : ""}` : "Consultas generales"}</h1>
        {t.case && <p className="muted" style={{ margin: "4px 0 0" }}>Expediente <span className="mono">{t.case.code}</span>{t.case.stage ? ` · Situación: ${t.case.stage}` : ""}</p>}
      </div>
      {urgent.length > 0 && (
        <div className="notice notice-danger" role="alert">
          <strong>Tiene {urgent.length === 1 ? "un aviso urgente" : `${urgent.length} avisos urgentes`} pendiente{urgent.length === 1 ? "" : "s"} de confirmar</strong>
          Léalo más abajo y pulse «He leído este aviso».
        </div>
      )}
      {t.missing_documents.length > 0 && <Missing t={t} onDone={setT} />}
      <div className="card stack">
        <h2 style={{ margin: 0 }}>Mensajes</h2>
        <div className="comm-list" role="log" aria-label="Mensajes" ref={box}>
          {t.messages.length === 0 && <p className="muted small">Todavía no hay mensajes. Puede escribirnos abajo.</p>}
          {t.messages.map((m) => <Bubble key={m.id} m={m} onChange={setT} />)}
        </div>
        <Write t={t} onDone={setT} writing={writing} />
      </div>
    </div>
  );
}

function Bubble({ m, onChange }: { m: PortalMsg; onChange: (t: PortalThread) => void }) {
  const [edit, setEdit] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const mine = m.author.type === "cliente";
  async function confirm() {
    try { onChange(await papi<PortalThread>(`/messages/${m.id}/confirm`, { method: "POST" })); } catch (e) { setErr(e instanceof ApiError ? e.message : "No se ha podido confirmar."); }
  }
  async function save() {
    try { onChange(await papi<PortalThread>(`/messages/${m.id}`, { method: "PATCH", body: JSON.stringify({ text: edit }) })); setEdit(null); }
    catch (e) { setErr(e instanceof ApiError ? e.message : "No se ha podido corregir."); }
  }
  return (
    <div className={`comm-msg ${mine ? "comm-out" : m.kind === "sistema" ? "comm-sys" : "comm-in"}`} aria-label={`Mensaje de ${mine ? "usted" : m.author.name}`}>
      <div className="comm-meta small"><strong>{mine ? "Usted" : m.author.name}</strong> · {fmtDateTime(m.created_at)}
        {m.level === "urgente" && <span className="badge badge-red">Urgente</span>}
        {m.level === "importante" && <span className="badge badge-yellow">Importante</span>}
        {m.edited_at && <span className="small">(corregido)</span>}</div>
      {edit === null ? <div style={{ whiteSpace: "pre-wrap" }}>{m.text}</div> : (
        <div className="stack" style={{ gap: 4 }}>
          <textarea aria-label="Corregir su mensaje" rows={3} value={edit} onChange={(e) => setEdit(e.target.value)} />
          <div className="row"><button className="btn btn-sm btn-primary" onClick={save}>Guardar</button><button className="btn btn-sm" onClick={() => setEdit(null)}>Cancelar</button></div>
        </div>
      )}
      {m.attachments.length > 0 && <ul className="comm-atts">{m.attachments.map((a) => <li key={a.id}><a href={`/api/v1/portal/attachments/${a.id}/file`} target="_blank" rel="noreferrer">📎 {a.name}</a></li>)}</ul>}
      {m.requires_confirmation && (m.confirmed_at
        ? <span className="small" style={{ color: "var(--ok)" }}>✓ Confirmado el {fmtDateTime(m.confirmed_at)}</span>
        : <button className="btn btn-primary btn-sm" onClick={confirm}>He leído este aviso</button>)}
      {mine && m.can_edit && edit === null && <button className="linklike small" style={{ alignSelf: "flex-start" }} onClick={() => setEdit(m.text)}>Corregir (15 minutos)</button>}
      {err && <span className="small" style={{ color: "var(--danger)" }} role="alert">{err}</span>}
    </div>
  );
}

function Missing({ t, onDone }: { t: PortalThread; onDone: (t: PortalThread) => void }) {
  const [busy, setBusy] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);
  async function upload(index: number, files: FileList | null) {
    if (!files?.length) return;
    setErr(null); setBusy(index);
    const f = new FormData();
    f.set("requirement_index", String(index));
    Array.from(files).forEach((x) => f.append("files", x));
    try { onDone(await sendForm(`/threads/${t.id}/messages`, f)); } catch (e) { setErr(e instanceof ApiError ? e.message : "No se ha podido enviar."); } finally { setBusy(null); }
  }
  return (
    <div className="card stack" aria-label="Documentos que faltan">
      <h2 style={{ margin: 0 }}>Documentos que faltan</h2>
      <p className="small muted" style={{ margin: 0 }}>Puede enviarlos en PDF o foto (JPG o PNG), de hasta 20 MB. Los revisaremos y le diremos si falta algo.</p>
      <ul className="stack" style={{ gap: 8, listStyle: "none", padding: 0, margin: 0 }}>
        {t.missing_documents.map((d) => (
          <li key={d.index} className="row" style={{ justifyContent: "space-between", borderBottom: "1px solid var(--line)", paddingBottom: 6 }}>
            <span>{d.label}{!d.required && <span className="small muted"> (si le corresponde)</span>}<br /><span className="small muted">{d.state}</span></span>
            <label className="btn btn-sm" style={{ cursor: "pointer" }}>
              {busy === d.index ? "Enviando…" : "Enviar"}
              <input type="file" multiple accept="application/pdf,image/jpeg,image/png" style={{ display: "none" }} aria-label={`Enviar ${d.label}`}
                onChange={(e) => upload(d.index, e.target.files)} disabled={busy !== null} />
            </label>
          </li>
        ))}
      </ul>
      {err && <div className="notice notice-danger small" role="alert">{err}</div>}
    </div>
  );
}

function Write({ t, onDone, writing }: { t: PortalThread; onDone: (t: PortalThread) => void; writing: React.MutableRefObject<boolean> }) {
  const [text, setText] = useState("");
  const [files, setFiles] = useState<FileList | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const ref = useRef<HTMLInputElement>(null);
  writing.current = !!text || !!files?.length;
  async function send(e: React.FormEvent) {
    e.preventDefault(); setErr(null); setBusy(true);
    const f = new FormData();
    f.set("text", text);
    Array.from(files ?? []).forEach((x) => f.append("files", x));
    try { onDone(await sendForm(`/threads/${t.id}/messages`, f)); setText(""); setFiles(null); if (ref.current) ref.current.value = ""; }
    catch (ex) { setErr(ex instanceof ApiError ? ex.message : "No se ha podido enviar."); } finally { setBusy(false); }
  }
  return (
    <form className="stack comm-composer" style={{ gap: 6 }} onSubmit={send}>
      <label className="small" htmlFor="portal-msg">Escriba su mensaje</label>
      <textarea id="portal-msg" rows={3} value={text} onChange={(e) => setText(e.target.value)} placeholder="Su consulta para el despacho" />
      <div className="row" style={{ gap: 6 }}>
        <input ref={ref} type="file" multiple accept="application/pdf,image/jpeg,image/png" aria-label="Adjuntar archivos" onChange={(e) => setFiles(e.target.files)} style={{ width: "auto" }} />
        <button className="btn btn-primary" disabled={busy || (!text.trim() && !files?.length)}>{busy ? "Enviando…" : "Enviar"}</button>
      </div>
      {err && <div className="notice notice-danger small" role="alert">{err}</div>}
    </form>
  );
}

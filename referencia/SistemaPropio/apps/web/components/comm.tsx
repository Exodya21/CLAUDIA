"use client";

// F2.3 + M12 fase 1 — Conversaciones con el cliente (lado del equipo). Portal propio, sin WhatsApp (T-31).
// Todo lo que se ve aquí sale de la API; los permisos los decide el servidor (`can`).

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, CSRF_HEADER, parseError } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";

export interface Att { id: string; name: string; mime: string; size: number; requirement_index: number | null; incorporated?: boolean }
export interface Msg {
  id: string; kind: string; visibility: "cliente" | "interna"; level: "normal" | "importante" | "urgente"; text: string;
  author: { type: "equipo" | "cliente" | "sistema"; name: string; id?: string }; created_at: string; edited_at: string | null;
  version: number; requires_confirmation: boolean; confirmed_at: string | null; attachments: Att[]; can_edit: boolean;
  read_by_client?: boolean; hidden?: boolean; hidden_reason?: string | null; template?: string | null;
  escalated_task_id?: string | null; unopened_48h?: boolean;
}
interface Template { code: string; name: string; level: string; task_kind: string | null }
interface TaskOpt { id: string; title: string; kind: string; start_at: string | null; legal_deadline: string | null; legal_status: string }
export interface PortalInfo { status: string; email?: string; invited_at?: string; terms_accepted_at?: string | null; last_login_at?: string | null; blocked_reason?: string | null }
interface ThreadData {
  id: string; kind: string; case: { id: string; code: string; title: string; materia: string } | null;
  contact: { id: string; name: string }; portal: PortalInfo; messages: Msg[]; search: string | null;
  missing_documents: { index: number; label: string; kind: string; state: string }[];
  templates: Template[]; tasks: TaskOpt[];
  can: { send: boolean; note: boolean; important: boolean; urgent: boolean; invite: boolean; export: boolean; incorporate: boolean };
}

const LEVEL_BADGE: Record<string, string> = { importante: "badge-yellow", urgente: "badge-red" };
const PORTAL_STATUS: Record<string, string> = {
  sin_acceso: "Sin acceso al portal", invitada: "Invitado/a, aún no ha entrado", activa: "Usa el portal", bloqueada: "Acceso bloqueado",
};

async function postForm<T>(path: string, form: FormData): Promise<T> {
  const res = await fetch(`/api/v1${path}`, { method: "POST", body: form, headers: CSRF_HEADER, credentials: "same-origin" });
  const data = await res.json().catch(() => null);
  if (!res.ok) throw parseError(res.status, data);
  return data as T;
}

function size(n: number) { return n > 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`; }

/** Hilo de un expediente (`caseId`), el general de un cliente (`contactId`) o uno ya conocido (`threadId`). */
export function CommThreadPanel({ caseId, contactId, threadId, compact = false }: { caseId?: string; contactId?: string; threadId?: string; compact?: boolean }) {
  const [d, setD] = useState<ThreadData | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const busy = useRef(false);
  const path = caseId ? `/comm/cases/${caseId}/thread` : contactId ? `/comm/contacts/${contactId}/thread` : `/comm/threads/${threadId}`;
  const load = useCallback(async (search?: string) => {
    try {
      const s = search ?? "";
      setD(await api<ThreadData>(`${path}${s ? `?q=${encodeURIComponent(s)}` : ""}`)); setErr(null);
    } catch (e) { setErr(e instanceof ApiError ? e.message : "No se pudo cargar la conversación"); }
  }, [path]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    const t = setInterval(() => { if (!busy.current && !q) load(); }, 15000);
    return () => clearInterval(t);
  }, [load, q]);
  if (err) return <div className="card"><h2>Conversación con el cliente</h2><div className="notice notice-warn" role="alert">{err}</div></div>;
  if (!d) return <div className="card"><p className="muted">Cargando conversación…</p></div>;
  const pending = d.messages.filter((m) => m.requires_confirmation && !m.confirmed_at && !m.hidden).length;
  return (
    <div className="card stack" aria-label="Conversación con el cliente">
      <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h2 style={{ margin: 0 }}>{d.case ? `Conversación · ${d.case.code}` : "Conversación general del cliente"}</h2>
          <p className="small muted" style={{ margin: "2px 0 0" }}>
            {d.contact.name} · {PORTAL_STATUS[d.portal.status] ?? d.portal.status}
            {d.portal.last_login_at ? ` · última entrada ${fmtDateTime(d.portal.last_login_at)}` : ""}
            {!compact && <> · <Link href={`/clientes/${d.contact.id}`}>ficha</Link></>}
            {d.case && !compact && <> · <Link href={`/expedientes/${d.case.id}`}>expediente</Link></>}
          </p>
        </div>
        <div className="row" style={{ gap: 6 }}>
          <form onSubmit={(e) => { e.preventDefault(); load(q); }} className="row" style={{ gap: 4 }}>
            <input aria-label="Buscar en la conversación" placeholder="Buscar…" value={q} onChange={(e) => setQ(e.target.value)} style={{ width: 150 }} />
            {q && <button type="button" className="btn btn-sm" onClick={() => { setQ(""); load(""); }}>×</button>}
          </form>
          {d.can.export && <>
            <a className="btn btn-sm" href={`/api/v1/comm/threads/${d.id}/export.pdf?scope=cliente`}>Exportar PDF</a>
            <a className="btn btn-sm" href={`/api/v1/comm/threads/${d.id}/export.pdf?scope=completo`} title="Incluye notas internas, ocultos y versiones">PDF completo (interno)</a>
          </>}
        </div>
      </div>
      {d.portal.status === "sin_acceso" && <div className="notice notice-info small">El cliente aún no tiene acceso al portal: no verá estos mensajes hasta que se le invite desde su ficha (pestaña «Portal»).</div>}
      {d.portal.status === "bloqueada" && <div className="notice notice-warn small">El acceso del cliente está bloqueado{d.portal.blocked_reason ? `: ${d.portal.blocked_reason}` : ""}.</div>}
      {pending > 0 && <div className="notice notice-warn small" role="status">{pending} aviso(s) urgente(s) sin confirmar por el cliente. A las 24 h se crea una tarea de llamada.</div>}
      <MessageList d={d} onChange={setD} />
      <Composer d={d} onSent={setD} busy={busy} />
    </div>
  );
}

function MessageList({ d, onChange }: { d: ThreadData; onChange: (t: ThreadData) => void }) {
  const box = useRef<HTMLDivElement>(null);
  // Baja al último mensaje dentro de la lista, sin mover la página
  useEffect(() => { if (box.current) box.current.scrollTop = box.current.scrollHeight; }, [d.messages.length]);
  if (!d.messages.length) return <p className="muted small">{d.search ? "Nada coincide con la búsqueda." : "Aún no hay mensajes en esta conversación."}</p>;
  return (
    <div className="comm-list" role="log" aria-label="Mensajes" ref={box}>
      {d.messages.map((m) => <Bubble key={m.id} m={m} d={d} onChange={onChange} />)}
    </div>
  );
}

function Bubble({ m, d, onChange }: { m: Msg; d: ThreadData; onChange: (t: ThreadData) => void }) {
  const [mode, setMode] = useState<"none" | "hide" | "edit" | "versions">("none");
  const [val, setVal] = useState("");
  const [versions, setVersions] = useState<{ version: number; text: string; replaced_at: string }[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const side = m.author.type === "cliente" ? "comm-in" : m.kind === "sistema" ? "comm-sys" : "comm-out";
  async function act(fn: () => Promise<ThreadData>) {
    setErr(null);
    try { onChange(await fn()); setMode("none"); } catch (e) { setErr(e instanceof ApiError ? e.message : "No se pudo completar"); }
  }
  return (
    <div className={`comm-msg ${side}${m.visibility === "interna" ? " comm-note" : ""}${m.hidden ? " comm-hidden" : ""}`} aria-label={`Mensaje de ${m.author.name}`}>
      <div className="comm-meta small">
        <strong>{m.author.name}</strong> · {fmtDateTime(m.created_at)}
        {m.visibility === "interna" && <span className="badge">Nota interna</span>}
        {m.level !== "normal" && <span className={`badge ${LEVEL_BADGE[m.level]}`}>{m.level === "urgente" ? "Urgente" : "Importante"}</span>}
        {m.version > 1 && <button className="linklike small" onClick={async () => { setMode("versions"); setVersions((await api<{ versions: typeof versions }>(`/comm/messages/${m.id}/versions`)).versions); }}>editado</button>}
        {m.hidden && <span className="badge badge-red">Oculto al cliente</span>}
      </div>
      <div style={{ whiteSpace: "pre-wrap" }}>{m.text}</div>
      {m.attachments.length > 0 && (
        <ul className="comm-atts">
          {m.attachments.map((a) => (
            <li key={a.id}>
              <a href={`/api/v1/comm/attachments/${a.id}/file`} target="_blank" rel="noreferrer">📎 {a.name}</a> <span className="muted small">({size(a.size)})</span>
              {a.requirement_index !== null && d.missing_documents && <span className="badge badge-blue small">para la lista del trámite</span>}
              {a.incorporated ? <span className="badge badge-green">En el expediente</span>
                : d.can.incorporate && m.author.type === "cliente" && <button className="btn btn-sm" onClick={() => act(() => api(`/comm/attachments/${a.id}/incorporate`, { method: "POST" }))}>Pasar al expediente</button>}
            </li>
          ))}
        </ul>
      )}
      <div className="comm-foot small muted">
        {m.visibility === "cliente" && m.author.type !== "cliente" && (m.read_by_client ? "✓ Leído por el cliente" : "No leído aún")}
        {m.requires_confirmation && (m.confirmed_at ? ` · Confirmado ${fmtDateTime(m.confirmed_at)}` : " · Pendiente de confirmar")}
        {m.unopened_48h && <span className="badge badge-yellow">Sin abrir en 48 h</span>}
        {m.escalated_task_id && <span className="badge badge-red">Tarea de llamada creada</span>}
        {m.hidden && m.hidden_reason && ` · Motivo: ${m.hidden_reason}`}
        <span style={{ marginLeft: "auto" }} />
        {m.can_edit && !m.hidden && <button className="linklike small" onClick={() => { setVal(m.text); setMode("edit"); }}>Corregir</button>}
        {d.can.send && !m.hidden && m.visibility === "cliente" && m.kind !== "sistema" && <button className="linklike small" onClick={() => { setVal(""); setMode("hide"); }}>Ocultar al cliente</button>}
      </div>
      {mode === "edit" && (
        <form className="stack" style={{ gap: 4 }} onSubmit={(e) => { e.preventDefault(); act(() => api(`/comm/messages/${m.id}`, { method: "PATCH", body: JSON.stringify({ text: val }) })); }}>
          <textarea aria-label="Texto corregido" rows={3} value={val} onChange={(e) => setVal(e.target.value)} />
          <div className="row"><button className="btn btn-sm btn-primary">Guardar corrección</button><button type="button" className="btn btn-sm" onClick={() => setMode("none")}>Cancelar</button>
            <span className="small muted">Se guarda la versión anterior.</span></div>
        </form>
      )}
      {mode === "hide" && (
        <form className="row" style={{ gap: 4 }} onSubmit={(e) => { e.preventDefault(); act(() => api(`/comm/messages/${m.id}/hide`, { method: "POST", body: JSON.stringify({ reason: val }) })); }}>
          <input aria-label="Motivo para ocultar" placeholder="Motivo (obligatorio)" value={val} onChange={(e) => setVal(e.target.value)} />
          <button className="btn btn-sm btn-danger" disabled={val.trim().length < 3}>Ocultar</button>
          <button type="button" className="btn btn-sm" onClick={() => setMode("none")}>Cancelar</button>
          <span className="small muted">No se borra: el despacho lo sigue viendo.</span>
        </form>
      )}
      {mode === "versions" && versions && (
        <div className="small" style={{ borderTop: "1px solid var(--line)", paddingTop: 4 }}>
          {versions.map((v) => <div key={v.version}><span className="muted">Versión {v.version} (sustituida {fmtDateTime(v.replaced_at)}):</span> {v.text}</div>)}
          <button className="linklike small" onClick={() => setMode("none")}>Cerrar</button>
        </div>
      )}
      {err && <div className="small" style={{ color: "var(--danger)" }} role="alert">{err}</div>}
    </div>
  );
}

function Composer({ d, onSent, busy }: { d: ThreadData; onSent: (t: ThreadData) => void; busy: React.MutableRefObject<boolean> }) {
  const [text, setText] = useState("");
  const [vis, setVis] = useState<"cliente" | "interna">(d.can.send ? "cliente" : "interna");
  const [level, setLevel] = useState("normal");
  const [tpl, setTpl] = useState("");
  const [task, setTask] = useState("");
  const [files, setFiles] = useState<FileList | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  busy.current = !!text || !!files?.length || !!tpl;
  if (!d.can.send && !d.can.note) return <p className="small muted">Su perfil puede leer esta conversación pero no escribir en ella.</p>;
  const allowed = d.templates.filter((t) => (t.level === "urgente" ? d.can.urgent : d.can.important));
  const chosen = d.templates.find((t) => t.code === tpl);
  const tasks = chosen?.task_kind ? d.tasks.filter((t) => t.kind === chosen.task_kind) : [];
  async function send(e: React.FormEvent) {
    e.preventDefault();
    setErr(null); setSending(true);
    const f = new FormData();
    f.set("text", text); f.set("visibility", vis); f.set("level", tpl ? "normal" : level);
    if (tpl) f.set("template", tpl);
    if (task) f.set("task_id", task);
    Array.from(files ?? []).forEach((x) => f.append("files", x));
    try {
      onSent(await postForm<ThreadData>(`/comm/threads/${d.id}/messages`, f));
      setText(""); setTpl(""); setTask(""); setLevel("normal"); setFiles(null); if (fileRef.current) fileRef.current.value = "";
    } catch (ex) { setErr(ex instanceof ApiError ? ex.message : "No se pudo enviar"); } finally { setSending(false); }
  }
  return (
    <form className="stack comm-composer" style={{ gap: 6 }} onSubmit={send} aria-label="Escribir">
      <div className="row" style={{ gap: 6 }}>
        <div className="segmented" role="radiogroup" aria-label="Para quién">
          {d.can.send && <button type="button" role="radio" aria-checked={vis === "cliente"} onClick={() => setVis("cliente")}>Mensaje al cliente</button>}
          {d.can.note && <button type="button" role="radio" aria-checked={vis === "interna"} onClick={() => { setVis("interna"); setTpl(""); setLevel("normal"); }}>Nota interna</button>}
        </div>
        {vis === "cliente" && !tpl && d.can.important && (
          <select aria-label="Nivel" value={level} onChange={(e) => setLevel(e.target.value)} style={{ width: "auto" }}>
            <option value="normal">Normal</option><option value="importante">Importante (aviso por correo)</option>
          </select>
        )}
        {vis === "cliente" && allowed.length > 0 && (
          <select aria-label="Plantilla" value={tpl} onChange={(e) => { setTpl(e.target.value); setTask(""); }} style={{ width: "auto" }}>
            <option value="">Sin plantilla</option>
            {allowed.map((t) => <option key={t.code} value={t.code}>{t.name}{t.level === "urgente" ? " (urgente)" : ""}</option>)}
          </select>
        )}
        {chosen?.task_kind && (
          <select aria-label="Tarea con la fecha" value={task} onChange={(e) => setTask(e.target.value)} style={{ width: "auto" }}>
            <option value="">Elija la tarea con la fecha…</option>
            {tasks.map((t) => <option key={t.id} value={t.id}>{t.title} · {t.legal_deadline ? `${t.legal_deadline} (${t.legal_status === "validado" ? "validado" : "sin validar"})` : t.start_at ? fmtDateTime(t.start_at) : "sin fecha"}</option>)}
          </select>
        )}
      </div>
      {tpl
        ? <div className="notice notice-info small">El texto sale de la plantilla{chosen?.task_kind ? " con la fecha de la tarea elegida (si es un plazo legal, solo si lo ha validado un letrado)" : ""}. El cliente lo verá en su portal{chosen?.level === "urgente" ? " y tendrá que confirmarlo; le llegará un correo sin el contenido" : ""}.</div>
        : <textarea aria-label={vis === "interna" ? "Nota interna" : "Mensaje al cliente"} rows={3} value={text} onChange={(e) => setText(e.target.value)}
            placeholder={vis === "interna" ? "Solo lo ve el equipo" : "Escriba al cliente (trato de usted)"} className={vis === "interna" ? "comm-note-input" : undefined} />}
      <div className="row" style={{ gap: 6 }}>
        {!tpl && <input ref={fileRef} type="file" multiple accept="application/pdf,image/jpeg,image/png" aria-label="Adjuntar archivos" onChange={(e) => setFiles(e.target.files)} style={{ width: "auto" }} />}
        <button className="btn btn-primary" disabled={sending || (!tpl && !text.trim() && !files?.length) || (!!chosen?.task_kind && !task)}>
          {sending ? "Enviando…" : vis === "interna" ? "Guardar nota" : "Enviar"}
        </button>
        {err && <span className="small" style={{ color: "var(--danger)" }} role="alert">{err}</span>}
      </div>
    </form>
  );
}

interface PortalStatus extends PortalInfo { emails: string[]; outbox: { at: string; subject: string; status: string; purpose: string }[]; can_invite: boolean }
const OUTBOX: Record<string, string> = { enviado: "Enviado", pendiente: "En cola", error: "Error, se reintentará", no_configurado: "No enviado: falta configurar el correo del despacho" };

/** Acceso del cliente al portal (ficha del cliente). */
export function PortalAccessCard({ contactId }: { contactId: string }) {
  const [s, setS] = useState<PortalStatus | null>(null);
  const [email, setEmail] = useState("");
  const [reason, setReason] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const load = useCallback(() => api<PortalStatus>(`/comm/contacts/${contactId}/portal`).then((r) => { setS(r); setEmail(r.email ?? r.emails[0] ?? ""); })
    .catch((e) => setMsg({ ok: false, text: e instanceof ApiError ? e.message : "No disponible" })), [contactId]);
  useEffect(() => { load(); }, [load]);
  async function act(path: string, body: unknown, ok: string) {
    setMsg(null);
    try { const r = await api<PortalStatus>(path, { method: "POST", body: JSON.stringify(body) }); setS(r); setMsg({ ok: true, text: ok }); setReason(""); }
    catch (e) { setMsg({ ok: false, text: e instanceof ApiError ? e.message : "No se pudo completar" }); }
  }
  if (!s) return <div className="card">{msg ? <div className="notice notice-warn">{msg.text}</div> : <p className="muted">Cargando…</p>}</div>;
  return (
    <div className="card stack" aria-label="Acceso al portal">
      <h2 style={{ margin: 0 }}>Portal del cliente</h2>
      <dl className="kv">
        <dt>Estado</dt><dd>{PORTAL_STATUS[s.status] ?? s.status}{s.blocked_reason ? ` (${s.blocked_reason})` : ""}</dd>
        {s.email && <><dt>Correo de acceso</dt><dd>{s.email}</dd></>}
        {s.terms_accepted_at && <><dt>Condiciones aceptadas</dt><dd>{fmtDateTime(s.terms_accepted_at)}</dd></>}
        {s.last_login_at && <><dt>Última entrada</dt><dd>{fmtDateTime(s.last_login_at)}</dd></>}
      </dl>
      {msg && <div className={`notice ${msg.ok ? "notice-ok" : "notice-danger"} small`} role="status">{msg.text}</div>}
      {s.can_invite && s.status !== "bloqueada" && (s.emails.length
        ? <form className="row" style={{ gap: 6 }} onSubmit={(e) => { e.preventDefault(); act(`/comm/contacts/${contactId}/portal/invite`, { email }, s.status === "sin_acceso" ? "Invitación enviada." : "Invitación reenviada."); }}>
            <select aria-label="Correo para el portal" value={email} onChange={(e) => setEmail(e.target.value)} style={{ width: "auto" }}>
              {s.emails.map((x) => <option key={x}>{x}</option>)}
            </select>
            <button className="btn btn-primary btn-sm">{s.status === "sin_acceso" ? "Dar acceso al portal" : "Reenviar invitación"}</button>
          </form>
        : <p className="small muted">Para darle acceso, añada antes un correo electrónico en sus datos de contacto.</p>)}
      {s.can_invite && s.status !== "sin_acceso" && (
        <form className="row" style={{ gap: 6 }} onSubmit={(e) => { e.preventDefault(); act(`/comm/contacts/${contactId}/portal/block`, { block: s.status !== "bloqueada", reason }, s.status === "bloqueada" ? "Acceso reactivado." : "Acceso bloqueado y sesiones cerradas."); }}>
          {s.status !== "bloqueada" && <input aria-label="Motivo del bloqueo" placeholder="Motivo del bloqueo" value={reason} onChange={(e) => setReason(e.target.value)} />}
          <button className={`btn btn-sm ${s.status === "bloqueada" ? "" : "btn-danger"}`} disabled={s.status !== "bloqueada" && reason.trim().length < 3}>{s.status === "bloqueada" ? "Reactivar acceso" : "Bloquear acceso"}</button>
        </form>
      )}
      {s.outbox.length > 0 && (
        <details><summary className="small">Últimos correos enviados al cliente</summary>
          <ul className="small" style={{ margin: "4px 0 0", paddingLeft: 18 }}>
            {s.outbox.map((o, i) => <li key={i}>{fmtDateTime(o.at)} · {o.subject} · <strong>{OUTBOX[o.status] ?? o.status}</strong></li>)}
          </ul>
          <p className="small muted">Los correos nunca llevan el contenido de los mensajes: solo avisan de que hay algo nuevo en el portal.</p>
        </details>
      )}
    </div>
  );
}

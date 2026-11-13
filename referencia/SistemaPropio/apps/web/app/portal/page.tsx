"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";
import { isAuthError, papi, type PortalMe, type PortalThreadRow } from "@/lib/portal";

export default function PortalHome() {
  const [me, setMe] = useState<PortalMe | null | undefined>(undefined);
  const load = useCallback(() => papi<PortalMe>("/me").then(setMe).catch((e) => { if (isAuthError(e)) setMe(null); else setMe(null); }), []);
  useEffect(() => { load(); }, [load]);
  if (me === undefined) return <p className="muted">Cargando…</p>;
  if (me === null) return <Access onDone={load} />;
  if (me.needs_terms) return <Terms me={me} onDone={load} />;
  return <Home me={me} onLogout={() => setMe(null)} />;
}

function Access({ onDone }: { onDone: () => void }) {
  const [step, setStep] = useState<"email" | "code">("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [info, setInfo] = useState<string | null>(null);
  const [devCode, setDevCode] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function ask(e: React.FormEvent) {
    e.preventDefault(); setErr(null); setBusy(true);
    try {
      const r = await papi<{ message: string; dev_code?: string }>("/auth/request-code", { method: "POST", body: JSON.stringify({ email }) });
      setInfo(r.message); setDevCode(r.dev_code ?? null); setStep("code");
    } catch (ex) { setErr(ex instanceof ApiError ? ex.message : "No se ha podido enviar el código."); } finally { setBusy(false); }
  }
  async function verify(e: React.FormEvent) {
    e.preventDefault(); setErr(null); setBusy(true);
    try { await papi("/auth/verify", { method: "POST", body: JSON.stringify({ email, code }) }); onDone(); }
    catch (ex) { setErr(ex instanceof ApiError ? ex.message : "No se ha podido comprobar el código."); } finally { setBusy(false); }
  }
  return (
    <div className="card stack portal-narrow">
      <h1 style={{ margin: 0 }}>Acceso a su portal</h1>
      {step === "email" ? (
        <form className="stack" onSubmit={ask}>
          <p className="muted" style={{ margin: 0 }}>Escriba el correo electrónico que facilitó al despacho. Le enviaremos un código de un solo uso.</p>
          <label>Correo electrónico<input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></label>
          <button className="btn btn-primary" disabled={busy}>{busy ? "Enviando…" : "Recibir código"}</button>
        </form>
      ) : (
        <form className="stack" onSubmit={verify}>
          {info && <div className="notice notice-info small" role="status">{info}</div>}
          {devCode && <div className="notice notice-warn small" role="status"><strong>Entorno de pruebas</strong>No hay correo configurado. Su código es <span className="mono">{devCode}</span>.</div>}
          <label>Código de 6 cifras<input inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6} required value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} /></label>
          <button className="btn btn-primary" disabled={busy || code.length !== 6}>{busy ? "Comprobando…" : "Entrar"}</button>
          <button type="button" className="linklike small" onClick={() => { setStep("email"); setCode(""); setDevCode(null); }}>Usar otro correo o pedir otro código</button>
        </form>
      )}
      {err && <div className="notice notice-danger small" role="alert">{err}</div>}
    </div>
  );
}

function Terms({ me, onDone }: { me: PortalMe; onDone: () => void }) {
  const [ok, setOk] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  async function accept() {
    try { await papi("/terms", { method: "POST", body: JSON.stringify({ accept: true }) }); onDone(); }
    catch (e) { setErr(e instanceof ApiError ? e.message : "No se ha podido guardar."); }
  }
  return (
    <div className="card stack portal-narrow">
      <h1 style={{ margin: 0 }}>Bienvenido/a, {me.name}</h1>
      <p style={{ margin: 0 }}>Antes de empezar, lea cómo funciona el portal:</p>
      <div className="notice notice-info" style={{ whiteSpace: "pre-wrap" }}>{me.terms}</div>
      <label className="row" style={{ gap: 8 }}><input type="checkbox" style={{ width: "auto" }} checked={ok} onChange={(e) => setOk(e.target.checked)} /> He leído y acepto las condiciones de uso del portal</label>
      <button className="btn btn-primary" disabled={!ok} onClick={accept}>Continuar</button>
      {err && <div className="notice notice-danger small" role="alert">{err}</div>}
    </div>
  );
}

function Home({ me, onLogout }: { me: PortalMe; onLogout: () => void }) {
  const [rows, setRows] = useState<PortalThreadRow[] | null>(null);
  useEffect(() => { papi<{ threads: PortalThreadRow[] }>("/threads").then((r) => setRows(r.threads)).catch(() => setRows([])); }, []);
  async function logout() { await papi("/auth/logout", { method: "POST" }).catch(() => null); onLogout(); }
  return (
    <div className="stack">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h1 style={{ margin: 0 }}>Hola, {me.name}</h1>
        <button className="btn btn-sm" onClick={logout}>Salir</button>
      </div>
      <p className="muted" style={{ margin: 0 }}>Aquí tiene sus asuntos con el despacho. Entre en cada uno para escribirnos, enviar documentos o ver nuestros avisos.</p>
      {rows === null && <p className="muted">Cargando…</p>}
      <div className="stack" style={{ gap: 10 }} aria-label="Sus asuntos">
        {rows?.map((t) => (
          <Link key={t.id} href={`/portal/asunto/${t.id}`} className="card portal-case">
            <div className="row" style={{ justifyContent: "space-between" }}>
              <strong>{t.case ? `${t.case.materia}${t.case.procedure ? ` · ${t.case.procedure}` : ""}` : "Consultas generales"}</strong>
              <span className="row" style={{ gap: 6 }}>
                {t.urgent_pending > 0 && <span className="badge badge-red">Aviso urgente</span>}
                {t.unread > 0 && <span className="count" aria-label={`${t.unread} mensajes nuevos`}>{t.unread}</span>}
              </span>
            </div>
            <span className="small muted">
              {t.case ? <>Expediente <span className="mono">{t.case.code}</span>{t.case.stage ? ` · ${t.case.stage}` : ""}</> : "Para lo que aún no es un expediente"}
              {t.last_message_at ? ` · último mensaje ${fmtDateTime(t.last_message_at)}` : ""}
            </span>
            {t.missing_documents > 0 && <span className="small" style={{ color: "#7a5a08" }}>Nos faltan {t.missing_documents} documento(s)</span>}
          </Link>
        ))}
      </div>
    </div>
  );
}

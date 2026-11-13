"use client";

import { useEffect, useState } from "react";
import { api, ApiError, fieldErrors, type AuthMode } from "@/lib/api";

interface DemoUser { username: string; full_name: string; description: string }
interface Enroll { username: string; otpauth_uri: string; secret: string; qr_svg: string }
type Step = "password" | "mfa" | "enroll";

const OIDC_ERRORS: Record<string, string> = {
  oidc_sin_mfa: "Su cuenta corporativa no confirmó la doble verificación (MFA). Actívela en su proveedor y vuelva a intentarlo.",
  oidc_sin_cuenta: "Esa cuenta corporativa no tiene acceso al sistema. Pida el alta a Dirección.",
  oidc_estado: "La respuesta del proveedor no corresponde a esta solicitud. Vuelva a intentarlo.",
  oidc_caducado: "El acceso corporativo ha caducado. Vuelva a intentarlo.",
  oidc_cancelado: "Se canceló el acceso en el proveedor corporativo.",
  oidc_token: "El proveedor corporativo devolvió una identidad no válida.",
  sesion_inactiva: "Su sesión se cerró por inactividad. Vuelva a entrar.",
  sesion_caducada: "Su sesión ha caducado. Vuelva a entrar.",
  sesion_revocada: "Su sesión se cerró desde la administración o desde otro dispositivo.",
};

export default function LoginPage() {
  const [mode, setMode] = useState<AuthMode | null>(null);
  const [users, setUsers] = useState<DemoUser[]>([]);
  const [step, setStep] = useState<Step>("password");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [newPass, setNewPass] = useState("");
  const [newPass2, setNewPass2] = useState("");
  const [enroll, setEnroll] = useState<Enroll | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});

  useEffect(() => {
    const e = new URLSearchParams(window.location.search).get("error");
    if (e) setError(OIDC_ERRORS[e] ?? (e.startsWith("sesion_") ? "Su sesión ha terminado. Vuelva a entrar." : "No se pudo completar el acceso corporativo."));
    api<AuthMode>("/auth/mode")
      .then((m) => {
        setMode(m);
        if (m.demo) return api<DemoUser[]>("/auth/demo/users").then(setUsers);
      })
      .catch(() => setError("No se puede contactar con la API. Compruebe que está en marcha."));
  }, []);

  function fail(e: unknown, fallback: string) {
    setError(e instanceof ApiError ? e.message : fallback);
    setFields(fieldErrors(e));
    setBusy(null);
  }

  async function submitPassword(ev: React.FormEvent) {
    ev.preventDefault();
    setBusy("password"); setError(null); setFields({});
    try {
      const r = await api<{ stage: "mfa" | "enroll" }>("/auth/login", { method: "POST", body: JSON.stringify({ username, password }) });
      setPassword("");
      if (r.stage === "enroll") {
        setEnroll(await api<Enroll>("/auth/enroll/start", { method: "POST" }));
      }
      setStep(r.stage);
      setBusy(null);
    } catch (e) { fail(e, "No se pudo iniciar sesión."); }
  }

  async function submitCode(ev: React.FormEvent) {
    ev.preventDefault();
    setBusy("mfa"); setError(null);
    try {
      await api("/auth/mfa", { method: "POST", body: JSON.stringify({ code }) });
      window.location.href = "/";
    } catch (e) {
      if (e instanceof ApiError && e.body.code === "verificacion_caducada") restart();
      fail(e, "Código no válido.");
      setCode("");
    }
  }

  async function submitEnroll(ev: React.FormEvent) {
    ev.preventDefault();
    setError(null); setFields({});
    if (newPass !== newPass2) { setFields({ new_password2: "Las dos contraseñas no coinciden" }); return; }
    setBusy("enroll");
    try {
      await api("/auth/enroll/confirm", { method: "POST", body: JSON.stringify({ code, new_password: newPass }) });
      window.location.href = "/";
    } catch (e) {
      if (e instanceof ApiError && e.body.code === "verificacion_caducada") restart();
      fail(e, "No se pudo activar la doble verificación.");
      setCode("");
    }
  }

  function restart() {
    setStep("password"); setEnroll(null); setCode(""); setNewPass(""); setNewPass2("");
  }

  async function enterDemo(u: string) {
    setBusy(u); setError(null);
    try {
      await api("/auth/demo/login", { method: "POST", body: JSON.stringify({ username: u }) });
      window.location.href = "/";
    } catch (e) { fail(e, "No se pudo iniciar sesión."); }
  }

  return (
    <div className="login-wrap">
      <div className="card login-card">
        <div className="brand" style={{ padding: 0, marginBottom: 18 }}>
          <div className="brand-mark" aria-hidden>SP</div>
          <div>
            <div className="brand-name">SISTEMA PROPIO</div>
            <div className="brand-sub">Acceso del personal</div>
          </div>
        </div>
        {error && <div className="notice notice-danger" role="alert" style={{ marginBottom: 14 }}>{error}</div>}
        {!mode && !error && <p className="muted">Comprobando el método de acceso…</p>}

        {mode?.local && step === "password" && (
          <form onSubmit={submitPassword} className="stack" aria-label="Acceso con usuario y contraseña">
            <h1 style={{ marginBottom: 0 }}>Entrar</h1>
            <label className="field">Usuario
              <input autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} required autoFocus />
            </label>
            <label className="field">Contraseña
              <input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
            </label>
            <button className="btn btn-primary" disabled={!!busy}>{busy === "password" ? "Comprobando…" : "Continuar"}</button>
            <p className="small muted" style={{ margin: 0 }}>
              Después se le pedirá el código de 6 cifras de su aplicación de autenticación.
              Tras 5 intentos fallidos el acceso se bloquea 15 minutos.
            </p>
          </form>
        )}

        {step === "mfa" && (
          <form onSubmit={submitCode} className="stack" aria-label="Código de verificación">
            <h1 style={{ marginBottom: 0 }}>Código de verificación</h1>
            <p className="muted" style={{ margin: 0 }}>Abra su aplicación de autenticación y escriba el código de 6 cifras de <strong>SISTEMA PROPIO</strong>.</p>
            <input inputMode="numeric" autoComplete="one-time-code" pattern="[0-9 ]{6,7}" maxLength={7} value={code}
              onChange={(e) => setCode(e.target.value)} required autoFocus aria-label="Código de 6 cifras"
              style={{ fontSize: 24, letterSpacing: 6, textAlign: "center" }} />
            <button className="btn btn-primary" disabled={!!busy}>{busy === "mfa" ? "Verificando…" : "Entrar"}</button>
            <button type="button" className="btn btn-sm" onClick={restart}>Volver</button>
          </form>
        )}

        {step === "enroll" && enroll && (
          <form onSubmit={submitEnroll} className="stack" aria-label="Primer acceso">
            <h1 style={{ marginBottom: 0 }}>Primer acceso</h1>
            <p className="muted" style={{ margin: 0 }}>Dos pasos para proteger su cuenta <span className="mono">{enroll.username}</span>.</p>
            <div>
              <h3>1. Active la doble verificación</h3>
              <p className="small" style={{ marginTop: 0 }}>
                Escanee este código con Microsoft Authenticator, Google Authenticator u otra aplicación compatible.
              </p>
              <div className="qr" aria-label="Código QR de configuración" dangerouslySetInnerHTML={{ __html: enroll.qr_svg }} />
              <p className="small muted">¿No puede escanear? Introduzca esta clave a mano:
                <br /><span className="mono" style={{ userSelect: "all" }}>{enroll.secret.match(/.{1,4}/g)?.join(" ")}</span></p>
            </div>
            <div className="stack">
              <h3 style={{ marginBottom: 0 }}>2. Elija su contraseña definitiva</h3>
              <label className="field">Nueva contraseña (mínimo 12 caracteres)
                <input type="password" autoComplete="new-password" value={newPass} onChange={(e) => setNewPass(e.target.value)}
                  className={fields.new_password ? "invalid" : undefined} required minLength={12} />
                {fields.new_password && <span className="error-text">{fields.new_password}</span>}
              </label>
              <label className="field">Repita la contraseña
                <input type="password" autoComplete="new-password" value={newPass2} onChange={(e) => setNewPass2(e.target.value)}
                  className={fields.new_password2 ? "invalid" : undefined} required />
                {fields.new_password2 && <span className="error-text">{fields.new_password2}</span>}
              </label>
              <label className="field">Código de 6 cifras que muestra ahora la aplicación
                <input inputMode="numeric" autoComplete="one-time-code" maxLength={7} value={code} onChange={(e) => setCode(e.target.value)}
                  className={fields.code ? "invalid" : undefined} required style={{ letterSpacing: 4 }} />
              </label>
            </div>
            <button className="btn btn-primary" disabled={!!busy}>{busy === "enroll" ? "Activando…" : "Activar y entrar"}</button>
            <button type="button" className="btn btn-sm" onClick={restart}>Cancelar</button>
          </form>
        )}

        {step === "password" && mode?.oidc_configured && (
          <div style={{ marginTop: 18 }}>
            <a className="btn" style={{ width: "100%", justifyContent: "center" }} href="/api/v1/auth/oidc/login">Entrar con la cuenta corporativa</a>
          </div>
        )}
        {step === "password" && mode?.oidc_requested && !mode.oidc_configured && (
          <p className="small muted" style={{ marginTop: 14 }}>Acceso con cuenta corporativa: no disponible aún (proveedor pendiente de elegir, decisión T-01).</p>
        )}

        {step === "password" && mode?.demo && (
          <details style={{ marginTop: 22 }} open>
            <summary><strong>Perfiles de demostración</strong> <span className="small muted">· solo entorno {mode.environment}</span></summary>
            <p className="muted small">
              Entrada sin contraseña con perfiles ficticios para comprobar qué ve cada rol. Este modo se bloquea
              por configuración en entornos compartidos y en producción.
            </p>
            <div className="user-grid" role="list">
              {users.map((u) => (
                <button key={u.username} role="listitem" className="user-option" disabled={!!busy} onClick={() => enterDemo(u.username)}>
                  <strong>{u.full_name}</strong>
                  <span className="muted small">{u.description}</span>
                  {busy === u.username && <span className="small"> · entrando…</span>}
                </button>
              ))}
            </div>
          </details>
        )}
      </div>
    </div>
  );
}

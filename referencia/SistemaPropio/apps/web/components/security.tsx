"use client";

import { useState } from "react";
import { api, ApiError, fieldErrors, type SessionInfo } from "@/lib/api";
import { ESTADOS_SESION, METODOS_ACCESO, deviceLabel, fmtDateTime, label } from "@/lib/format";

/** Tabla de sesiones. `onRevoke` recibe la sesión; si no se pasa, no hay botón. */
export function SessionsTable({ rows, onRevoke }: { rows: SessionInfo[]; onRevoke?: (s: SessionInfo) => void }) {
  if (!rows.length) return <p className="empty">Sin sesiones registradas.</p>;
  return (
    <div className="table-wrap">
      <table className="data">
        <thead><tr><th>Inicio</th><th>Último uso</th><th>Dispositivo</th><th>Método</th><th>Estado</th><th></th></tr></thead>
        <tbody>
          {rows.map((s) => (
            <tr key={s.id}>
              <td>{fmtDateTime(s.created_at)}</td>
              <td>{fmtDateTime(s.last_seen_at)}</td>
              <td>{deviceLabel(s.user_agent)}{s.ip && <div className="small muted mono">{s.ip}</div>}</td>
              <td className="small">{label(METODOS_ACCESO, s.auth_method)}</td>
              <td>
                {s.state === "activa" ? <span className="badge badge-green">Activa</span> : <span className="badge">{label(ESTADOS_SESION, s.state)}</span>}
                {s.current && <span className="badge badge-blue" style={{ marginLeft: 6 }}>Esta</span>}
                {s.revoke_reason && s.state === "revocada" && <div className="small muted">{s.revoke_reason}</div>}
              </td>
              <td>{onRevoke && s.state === "activa" && !s.current && (
                <button className="btn btn-sm" onClick={() => onRevoke(s)}>Cerrar</button>
              )}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function PasswordChange() {
  const [cur, setCur] = useState("");
  const [n1, setN1] = useState("");
  const [n2, setN2] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setMsg(null); setFields({});
    if (n1 !== n2) { setFields({ new_password2: "No coinciden" }); return; }
    setBusy(true);
    try {
      await api("/auth/password", { method: "POST", body: JSON.stringify({ current_password: cur, new_password: n1 }) });
      setMsg({ ok: true, text: "Contraseña cambiada. Se han cerrado sus sesiones en otros dispositivos." });
      setCur(""); setN1(""); setN2("");
    } catch (err) {
      setFields(fieldErrors(err));
      setMsg({ ok: false, text: err instanceof ApiError ? err.message : "No se pudo cambiar." });
    } finally { setBusy(false); }
  }

  return (
    <form onSubmit={submit} className="stack" aria-label="Cambiar contraseña">
      <h3 style={{ margin: 0 }}>Cambiar contraseña</h3>
      {msg && <div className={`notice ${msg.ok ? "notice-ok" : "notice-danger"}`}>{msg.text}</div>}
      <div className="form-grid">
        <label className="field full">Contraseña actual
          <input type="password" autoComplete="current-password" value={cur} onChange={(e) => setCur(e.target.value)} required
            className={fields.current_password ? "invalid" : undefined} />
        </label>
        <label className="field">Nueva (mínimo 12 caracteres)
          <input type="password" autoComplete="new-password" value={n1} onChange={(e) => setN1(e.target.value)} required minLength={12}
            className={fields.new_password ? "invalid" : undefined} />
          {fields.new_password && <span className="error-text">{fields.new_password}</span>}
        </label>
        <label className="field">Repítala
          <input type="password" autoComplete="new-password" value={n2} onChange={(e) => setN2(e.target.value)} required
            className={fields.new_password2 ? "invalid" : undefined} />
          {fields.new_password2 && <span className="error-text">{fields.new_password2}</span>}
        </label>
      </div>
      <div><button className="btn btn-primary" disabled={busy}>{busy ? "Guardando…" : "Cambiar contraseña"}</button></div>
    </form>
  );
}

/** Formulario con motivo obligatorio para acciones administrativas (no usa diálogos del navegador). */
export function ReasonForm({ action, danger, placeholder, onSubmit, onCancel }: {
  action: string; danger?: boolean; placeholder?: string; onSubmit: (reason: string) => Promise<void>; onCancel: () => void;
}) {
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  return (
    <form className="row" style={{ alignItems: "flex-start", gap: 8, marginTop: 8 }} onSubmit={async (e) => {
      e.preventDefault(); setBusy(true); setError(null);
      try { await onSubmit(reason); } catch (err) { setError(err instanceof ApiError ? err.message : "No se pudo completar."); setBusy(false); }
    }}>
      <div style={{ flex: 1, minWidth: 220 }}>
        <input aria-label="Motivo" placeholder={placeholder ?? "Motivo (queda en la auditoría)"} value={reason}
          onChange={(e) => setReason(e.target.value)} minLength={5} required autoFocus />
        {error && <span className="error-text">{error}</span>}
      </div>
      <button className={`btn btn-sm ${danger ? "btn-warn" : "btn-primary"}`} disabled={busy}>{busy ? "…" : action}</button>
      <button type="button" className="btn btn-sm" onClick={onCancel}>Cancelar</button>
    </form>
  );
}

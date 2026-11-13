"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AgentsAdmin } from "@/components/agents_admin";
import { useMe } from "@/components/session";
import { MembershipFields, MfaBadge, TempPasswordCard, membershipBody } from "@/components/admin";
import { api, ApiError, backupValid, fieldErrors, hasPerm, type AdminCatalog, type AdminUser, type BackupRun, type TempPassword } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";

export default function Administracion() {
  const me = useMe();
  const canUsers = hasPerm(me, "admin.users.manage");
  const canAgents = hasPerm(me, "agents.manage");
  const [tab, setTab] = useState<"usuarios" | "agentes">(canUsers ? "usuarios" : "agentes");
  if (!canUsers && !canAgents) {
    return <div className="notice notice-warn"><strong>Sin acceso</strong>Solo Dirección administra usuarios y agentes.</div>;
  }
  return (
    <div className="stack">
      {canUsers && canAgents && (
        <div className="tabs" role="tablist" style={{ marginBottom: 0 }}>
          <button role="tab" aria-selected={tab === "usuarios"} onClick={() => setTab("usuarios")}>Usuarios y copias</button>
          <button role="tab" aria-selected={tab === "agentes"} onClick={() => setTab("agentes")}>Agentes automáticos</button>
        </div>
      )}
      {tab === "usuarios" && canUsers && <AdminHome canBackups={hasPerm(me, "admin.backups.read")} />}
      {tab === "agentes" && canAgents && (
        <div className="stack">
          <h1>Agentes automáticos</h1>
          <AgentsAdmin />
        </div>
      )}
    </div>
  );
}

function AdminHome({ canBackups }: { canBackups: boolean }) {
  const [users, setUsers] = useState<AdminUser[] | null>(null);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [catalog, setCatalog] = useState<AdminCatalog | null>(null);
  const [creating, setCreating] = useState(false);
  const [created, setCreated] = useState<TempPassword | null>(null);

  const load = () => {
    const qs = new URLSearchParams();
    if (q) qs.set("q", q);
    if (status) qs.set("status", status);
    api<AdminUser[]>(`/admin/users?${qs}`).then(setUsers).catch(() => setUsers([]));
  };
  useEffect(() => { load(); }, [status]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { api<AdminCatalog>("/admin/catalog").then(setCatalog).catch(() => undefined); }, []);

  return (
    <div className="stack">
      <div className="topline">
        <div>
          <h1>Administración</h1>
          <p className="subtitle">Usuarios, roles y sesiones de sus entidades. Cada cambio exige motivo y queda en la auditoría.</p>
        </div>
        {!creating && <button className="btn btn-primary" onClick={() => { setCreating(true); setCreated(null); }}>+ Nuevo usuario</button>}
      </div>

      {created && <TempPasswordCard data={created} onClose={() => setCreated(null)} />}
      {creating && catalog && (
        <NewUser catalog={catalog} onCancel={() => setCreating(false)}
          onCreated={(r) => { setCreating(false); setCreated(r); load(); }} />
      )}

      <div className="card">
        <form className="row" onSubmit={(e) => { e.preventDefault(); load(); }}>
          <input className="search" placeholder="Buscar por nombre, usuario o correo" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Buscar usuarios" />
          <select style={{ width: 170 }} value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Estado">
            <option value="">Todos</option><option value="activo">Activos</option><option value="inactivo">Desactivados</option>
          </select>
          <button className="btn">Buscar</button>
        </form>
        <div className="table-wrap" style={{ marginTop: 12 }}>
          <table className="data">
            <thead><tr><th>Persona</th><th>Roles vigentes</th><th>Acceso</th><th>Último acceso</th><th>Sesiones</th></tr></thead>
            <tbody>
              {users?.length === 0 && <tr><td colSpan={5} className="empty">Sin resultados.</td></tr>}
              {users?.map((u) => (
                <tr key={u.id}>
                  <td><Link href={`/administracion/${u.id}`}><strong>{u.full_name}</strong></Link><div className="small muted mono">{u.username}</div></td>
                  <td className="small">{u.memberships.filter((m) => m.status === "activa").map((m) => (
                    <div key={m.id}>{m.role_name} · <span className="muted">{m.organization}{m.branch ? ` · ${m.branch}` : ""}</span></div>
                  ))}</td>
                  <td><MfaBadge u={u} /></td>
                  <td className="small">{u.last_login_at ? fmtDateTime(u.last_login_at) : "—"}</td>
                  <td>{u.active_sessions || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      {canBackups && <Backups />}
    </div>
  );
}

function NewUser({ catalog, onCancel, onCreated }: { catalog: AdminCatalog; onCancel: () => void; onCreated: (r: TempPassword) => void }) {
  const [f, setF] = useState({ username: "", full_name: "", email: "", reason: "" });
  const [m, setM] = useState<Record<string, string>>({ organization_id: catalog.organizations[0]?.id ?? "", role_code: "", branch_id: "", department_id: "" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setError(null); setErrors({});
    try {
      onCreated(await api<TempPassword>("/admin/users", { method: "POST", body: JSON.stringify({ ...f, membership: membershipBody(m) }) }));
    } catch (err) {
      const fe = fieldErrors(err);
      setErrors(Object.fromEntries(Object.entries(fe).map(([k, v]) => [k.replace("membership.", ""), v])));
      setError(err instanceof ApiError ? err.message : "No se pudo crear.");
      setBusy(false);
    }
  }
  const field = (k: keyof typeof f, lbl: string, extra: React.InputHTMLAttributes<HTMLInputElement> = {}) => (
    <label className="field">{lbl}
      <input value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} className={errors[k] ? "invalid" : undefined} required {...extra} />
      {errors[k] && <span className="error-text">{errors[k]}</span>}
    </label>
  );
  return (
    <form className="card" onSubmit={submit} aria-label="Nuevo usuario">
      <h2 style={{ marginTop: 0 }}>Nuevo usuario</h2>
      {error && <div className="notice notice-danger" style={{ marginBottom: 12 }}>{error}</div>}
      <div className="form-grid">
        {field("full_name", "Nombre y apellidos")}
        {field("username", "Usuario (minúsculas, sin espacios)", { pattern: "[a-z0-9][a-z0-9._-]{2,79}", placeholder: "nombre.apellido" })}
        {field("email", "Correo corporativo", { type: "email" })}
        <span />
        <MembershipFields catalog={catalog} value={m} onChange={setM} errors={errors} />
        <label className="field full">Motivo del alta
          <input value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })} minLength={5} required placeholder="p. ej. incorporación a Laboral Barcelona" />
        </label>
      </div>
      <p className="small muted">Se generará una contraseña provisional que solo se mostrará una vez. En su primer acceso, la persona elegirá su contraseña y activará la doble verificación con el móvil.</p>
      <div className="row">
        <button className="btn btn-primary" disabled={busy}>{busy ? "Creando…" : "Crear usuario"}</button>
        <button type="button" className="btn" onClick={onCancel}>Cancelar</button>
      </div>
    </form>
  );
}

function Backups() {
  const [rows, setRows] = useState<BackupRun[] | null>(null);
  useEffect(() => { api<BackupRun[]>("/admin/backups").then(setRows).catch(() => setRows([])); }, []);
  const lastValid = useMemo(() => rows?.find(backupValid), [rows]);
  const ageH = lastValid ? (Date.now() - new Date(lastValid.created_at).getTime()) / 36e5 : null;
  return (
    <div className="card">
      <h2>Copias de seguridad</h2>
      {rows && !lastValid && (
        <div className="notice notice-danger">No hay ninguna copia comprobada. Ejecute <span className="mono">COPIA_SEGURIDAD.bat</span> en el ordenador donde está instalado el sistema.</div>
      )}
      {lastValid && ageH !== null && (
        <div className={`notice ${ageH > 26 ? "notice-warn" : "notice-ok"}`}>
          Última copia válida: {fmtDateTime(lastValid.created_at)} ({ageH < 1 ? "hace menos de una hora" : `hace ${Math.round(ageH)} h`}).
          {ageH > 26 && " Han pasado más de 24 horas: haga una copia nueva."}
        </div>
      )}
      <p className="small muted">Cada copia se restaura en una base aparte y se comprueba que el esquema existe y que la cadena de auditoría está íntegra y coincide con la base en uso (AT-29).</p>
      <div className="table-wrap">
        <table className="data">
          <thead><tr><th>Fecha</th><th>Archivo</th><th>Tamaño</th><th>Auditoría</th><th>Resultado</th></tr></thead>
          <tbody>
            {rows?.length === 0 && <tr><td colSpan={5} className="empty">Todavía no se ha hecho ninguna copia.</td></tr>}
            {rows?.map((b) => (
              <tr key={b.id}>
                <td>{fmtDateTime(b.created_at)}</td>
                <td className="mono small">{b.file_name}<div className="muted" title={b.sha256 ?? ""}>sha256 {b.sha256?.slice(0, 12)}…</div></td>
                <td className="small">{b.size_bytes ? `${(b.size_bytes / 1024).toFixed(0)} KB` : "—"}</td>
                <td className="small">{b.audit_events ?? "—"} eventos</td>
                <td>{backupValid(b) ? <span className="badge badge-green">Válida</span> : <span className="badge badge-red">No válida</span>}
                  <div className="small muted">{b.detail}</div></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

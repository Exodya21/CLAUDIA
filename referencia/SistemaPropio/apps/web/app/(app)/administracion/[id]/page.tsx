"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { MembershipFields, MfaBadge, TempPasswordCard, membershipBody } from "@/components/admin";
import { ReasonForm, SessionsTable } from "@/components/security";
import { useMe } from "@/components/session";
import { api, ApiError, fieldErrors, type AdminCatalog, type AdminUserDetail, type TempPassword } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";

type Pending = { kind: "deactivate" | "reactivate" | "reset" | "revoke_all" } | { kind: "end"; id: string } | { kind: "revoke"; id: string };

export default function UserDetail() {
  const { id } = useParams<{ id: string }>();
  const me = useMe();
  const [u, setU] = useState<AdminUserDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<Pending | null>(null);
  const [temp, setTemp] = useState<TempPassword | null>(null);
  const [catalog, setCatalog] = useState<AdminCatalog | null>(null);
  const [adding, setAdding] = useState(false);

  const load = () => api<AdminUserDetail>(`/admin/users/${id}`).then(setU)
    .catch((e) => setError(e instanceof ApiError ? e.message : "No se pudo cargar."));
  useEffect(() => { load(); }, [id]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { api<AdminCatalog>("/admin/catalog").then(setCatalog).catch(() => undefined); }, []);

  if (error) return <div className="notice notice-danger">{error} <Link href="/administracion">Volver</Link></div>;
  if (!u) return <p className="muted">Cargando…</p>;
  const self = u.id === me.id;
  const post = async (path: string, reason: string) => {
    const r = await api<unknown>(path, { method: "POST", body: JSON.stringify({ reason }) });
    setPending(null);
    await load();
    return r;
  };

  return (
    <div className="stack">
      <div className="topline">
        <div>
          <p className="small"><Link href="/administracion">← Administración</Link></p>
          <h1>{u.full_name}</h1>
          <p className="subtitle"><span className="mono">{u.username}</span> · {u.email} · alta {fmtDateTime(u.created_at)}</p>
        </div>
        <MfaBadge u={u} />
      </div>

      {temp && <TempPasswordCard data={temp} onClose={() => setTemp(null)} />}

      <div className="card">
        <h2>Cuenta</h2>
        <dl className="kv">
          <dt>Estado</dt><dd>{u.status === "activo" ? "Activo" : "Desactivado"}</dd>
          <dt>Doble verificación</dt><dd>{u.mfa_enrolled ? "Activada" : "Sin activar"}</dd>
          <dt>Último acceso</dt><dd>{u.last_login_at ? fmtDateTime(u.last_login_at) : "Nunca"}</dd>
          {u.is_demo && <><dt>Tipo</dt><dd>Perfil ficticio de demostración</dd></>}
        </dl>
        {self ? <p className="small muted">Es su propia cuenta: sus credenciales se gestionan en Ajustes → Seguridad.</p> : (
          <div className="row" style={{ marginTop: 12 }}>
            {u.status === "activo" ? <>
              <button className="btn btn-sm" onClick={() => setPending({ kind: "reset" })}>Restablecer contraseña y móvil</button>
              <button className="btn btn-sm" onClick={() => setPending({ kind: "revoke_all" })} disabled={!u.active_sessions}>Cerrar todas sus sesiones</button>
              <button className="btn btn-sm btn-warn" onClick={() => setPending({ kind: "deactivate" })}>Desactivar</button>
            </> : <button className="btn btn-sm btn-primary" onClick={() => setPending({ kind: "reactivate" })}>Reactivar</button>}
          </div>
        )}
        {pending?.kind === "reset" && <ReasonForm action="Restablecer" placeholder="Motivo, p. ej. cambio de móvil" onCancel={() => setPending(null)}
          onSubmit={async (r) => { setTemp(await post(`/admin/users/${u.id}/reset-credentials`, r) as TempPassword); }} />}
        {pending?.kind === "deactivate" && <ReasonForm action="Desactivar" danger placeholder="Motivo, p. ej. fin de contrato" onCancel={() => setPending(null)}
          onSubmit={async (r) => { await post(`/admin/users/${u.id}/deactivate`, r); }} />}
        {pending?.kind === "reactivate" && <ReasonForm action="Reactivar" onCancel={() => setPending(null)}
          onSubmit={async (r) => { await post(`/admin/users/${u.id}/reactivate`, r); }} />}
        {pending?.kind === "revoke_all" && <ReasonForm action="Cerrar sesiones" danger onCancel={() => setPending(null)}
          onSubmit={async (r) => { await post(`/admin/users/${u.id}/revoke-sessions`, r); }} />}
      </div>

      <div className="card">
        <div className="row">
          <h2 style={{ margin: 0 }}>Roles y ámbitos</h2>
          <span className="spacer" />
          {!adding && <button className="btn btn-sm" onClick={() => setAdding(true)}>+ Añadir rol</button>}
        </div>
        <p className="small muted">Un cambio de rol se hace añadiendo el nuevo y retirando el anterior: el historial se conserva. El efecto es inmediato, también en sesiones abiertas.</p>
        {adding && catalog && <AddMembership userId={u.id} catalog={catalog} onCancel={() => setAdding(false)} onDone={() => { setAdding(false); load(); }} />}
        <div className="table-wrap">
          <table className="data">
            <thead><tr><th>Rol</th><th>Entidad</th><th>Sede</th><th>Departamento</th><th>Vigencia</th><th></th></tr></thead>
            <tbody>
              {u.memberships.map((m) => (
                <tr key={m.id}>
                  <td><strong>{m.role_name}</strong></td>
                  <td className="small">{m.organization}</td>
                  <td className="small">{m.branch ?? "Todas"}</td>
                  <td className="small">{m.department ?? "—"}</td>
                  <td className="small">
                    {m.status === "activa" ? <span className="badge badge-green">Vigente</span> : <span className="badge">{m.status === "finalizada" ? "Retirado" : m.status}</span>}
                    <div className="muted">desde {fmtDateTime(m.valid_from)}{m.valid_to ? ` hasta ${fmtDateTime(m.valid_to)}` : ""}</div>
                  </td>
                  <td>{m.status === "activa" && m.manageable && <button className="btn btn-sm" onClick={() => setPending({ kind: "end", id: m.id })}>Retirar</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {pending?.kind === "end" && <ReasonForm action="Retirar rol" danger onCancel={() => setPending(null)}
          onSubmit={async (r) => { await post(`/admin/memberships/${pending.id}/end`, r); }} />}
      </div>

      <div className="card">
        <h2>Sesiones</h2>
        <SessionsTable rows={u.sessions} onRevoke={(s) => setPending({ kind: "revoke", id: s.id })} />
        {pending?.kind === "revoke" && <ReasonForm action="Confirmar cierre" danger placeholder="Motivo, p. ej. dispositivo perdido" onCancel={() => setPending(null)}
          onSubmit={async (r) => { await post(`/admin/sessions/${pending.id}/revoke`, r); }} />}
      </div>
    </div>
  );
}

function AddMembership({ userId, catalog, onCancel, onDone }: { userId: string; catalog: AdminCatalog; onCancel: () => void; onDone: () => void }) {
  const [m, setM] = useState<Record<string, string>>({ organization_id: catalog.organizations[0]?.id ?? "", role_code: "", branch_id: "", department_id: "" });
  const [reason, setReason] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  async function submit(e: React.FormEvent) {
    e.preventDefault(); setError(null); setErrors({});
    try {
      await api(`/admin/users/${userId}/memberships`, { method: "POST", body: JSON.stringify({ ...membershipBody(m), reason }) });
      onDone();
    } catch (err) { setErrors(fieldErrors(err)); setError(err instanceof ApiError ? err.message : "No se pudo añadir."); }
  }
  return (
    <form className="card" style={{ background: "var(--surface-2)", margin: "10px 0" }} onSubmit={submit}>
      {error && <div className="notice notice-danger" style={{ marginBottom: 10 }}>{error}</div>}
      <div className="form-grid">
        <MembershipFields catalog={catalog} value={m} onChange={setM} errors={errors} />
        <label className="field full">Motivo
          <input value={reason} onChange={(e) => setReason(e.target.value)} minLength={5} required />
        </label>
      </div>
      <div className="row" style={{ marginTop: 10 }}>
        <button className="btn btn-primary btn-sm">Añadir rol</button>
        <button type="button" className="btn btn-sm" onClick={onCancel}>Cancelar</button>
      </div>
    </form>
  );
}

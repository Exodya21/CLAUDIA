"use client";

import { useState } from "react";
import type { AdminCatalog, AdminUser, TempPassword } from "@/lib/api";

export function MfaBadge({ u }: { u: AdminUser }) {
  if (u.status !== "activo") return <span className="badge">Desactivado</span>;
  if (u.is_demo && !u.has_password) return <span className="badge">Solo demo</span>;
  if (u.must_change_password || !u.mfa_enrolled) return <span className="badge badge-yellow">Pendiente de primer acceso</span>;
  return <span className="badge badge-green">Contraseña + móvil</span>;
}

export function TempPasswordCard({ data, onClose }: { data: TempPassword; onClose: () => void }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="card" role="status">
      <h2 style={{ marginTop: 0 }}>Contraseña provisional de {data.user.full_name}</h2>
      <div className="secret-box">
        <div className="small">Usuario: <span className="mono">{data.user.username}</span></div>
        <div className="mono">{data.temporary_password}</div>
      </div>
      <p className="small">{data.notice}</p>
      <div className="row">
        <button className="btn btn-sm" onClick={() => navigator.clipboard?.writeText(data.temporary_password).then(() => setCopied(true)).catch(() => undefined)}>
          {copied ? "Copiada" : "Copiar"}
        </button>
        <button className="btn btn-sm btn-primary" onClick={onClose}>Ya la he entregado</button>
      </div>
    </div>
  );
}

export function MembershipFields({ catalog, value, onChange, errors }: {
  catalog: AdminCatalog; value: Record<string, string>; onChange: (v: Record<string, string>) => void; errors: Record<string, string>;
}) {
  const org = catalog.organizations.find((o) => o.id === value.organization_id);
  const role = catalog.roles.find((r) => r.code === value.role_code);
  const set = (k: string, v: string) => onChange({ ...value, [k]: v, ...(k === "organization_id" ? { branch_id: "", department_id: "" } : {}) });
  return (
    <>
      <label className="field">Entidad
        <select value={value.organization_id} onChange={(e) => set("organization_id", e.target.value)} required>
          <option value="">Elija…</option>
          {catalog.organizations.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
        </select>
      </label>
      <label className="field">Rol
        <select value={value.role_code} onChange={(e) => set("role_code", e.target.value)} required>
          <option value="">Elija…</option>
          {catalog.roles.map((r) => <option key={r.code} value={r.code}>{r.name}</option>)}
        </select>
        {role && <span className="hint">{role.description}</span>}
      </label>
      <label className="field">Sede <span className="hint">vacía = todas las sedes</span>
        <select value={value.branch_id} onChange={(e) => set("branch_id", e.target.value)} disabled={!org} className={errors.branch_id ? "invalid" : undefined}>
          <option value="">Todas</option>
          {org?.branches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
        </select>
      </label>
      <label className="field">Departamento <span className="hint">vacío = sin acotar</span>
        <select value={value.department_id} onChange={(e) => set("department_id", e.target.value)} disabled={!org} className={errors.department_id ? "invalid" : undefined}>
          <option value="">Sin departamento</option>
          {org?.departments.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select>
      </label>
    </>
  );
}

export function membershipBody(v: Record<string, string>) {
  return { organization_id: v.organization_id, role_code: v.role_code, branch_id: v.branch_id || null, department_id: v.department_id || null };
}


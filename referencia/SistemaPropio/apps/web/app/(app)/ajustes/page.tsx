"use client";

import { useEffect, useState } from "react";
import { useMe } from "@/components/session";
import { PasswordChange, SessionsTable } from "@/components/security";
import { Pager } from "@/components/ui";
import { api, ApiError, hasPerm, type AuditEvent, type Page, type SessionInfo } from "@/lib/api";
import { ACCIONES_AUDITORIA, METODOS_ACCESO, fmtDateTime, label, toLocalInput } from "@/lib/format";

interface Grant { id: string; username: string; case_code: string; reason: string; created_at: string; expires_at: string; revoked_at: string | null }

export default function Ajustes() {
  const me = useMe();
  const [catalog, setCatalog] = useState<Record<string, string>>({});
  useEffect(() => { api<Record<string, string>>("/permissions").then(setCatalog).catch(() => undefined); }, []);

  return (
    <div className="stack">
      <div className="topline">
        <div>
          <h1>Ajustes</h1>
          <p className="subtitle">Su perfil, su seguridad de acceso y lo que el servidor le permite hacer.</p>
        </div>
      </div>
      <div className="grid grid-2">
        <div className="card">
          <h2>Perfil</h2>
          <dl className="kv">
            <dt>Nombre</dt><dd>{me.full_name}</dd>
            <dt>Usuario</dt><dd className="mono">{me.username}</dd>
            <dt>Correo</dt><dd>{me.email}</dd>
            <dt>Acceso</dt><dd>{label(METODOS_ACCESO, me.auth_mode)}</dd>
            <dt>Zona horaria</dt><dd>Europe/Madrid</dd>
          </dl>
        </div>
        <div className="card">
          <h2>Ámbitos</h2>
          <ul>{me.memberships.map((m, i) => (
            <li key={i}><strong>{m.role_name}</strong> · {m.organization.name} · {m.branch ?? "todas las sedes"} · {m.department ?? "sin departamento"}</li>
          ))}</ul>
        </div>
      </div>
      <Security hasPassword={me.has_password} />
      <div className="card">
        <h2>Permisos efectivos</h2>
        <p className="muted small">Calculados por el servidor. Cualquier permiso que no aparezca aquí está denegado.</p>
        {me.memberships.filter((m, i, a) => a.findIndex((x) => x.organization.id === m.organization.id) === i).map((m) => (
          <div key={m.organization.id} style={{ marginBottom: 14 }}>
            <h3>{m.organization.name}</h3>
            <table className="data">
              <tbody>
                {(me.permissions[m.organization.id] ?? []).map((p) => (
                  <tr key={p}><td className="mono" style={{ width: 240 }}>{p}</td><td>{catalog[p] ?? ""}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </div>
      {hasPerm(me, "grant.manage") && <Grants />}
      {hasPerm(me, "audit.read") && <Audit />}
    </div>
  );
}

function Security({ hasPassword }: { hasPassword: boolean }) {
  const [rows, setRows] = useState<SessionInfo[]>([]);
  const load = () => api<SessionInfo[]>("/auth/sessions").then(setRows).catch(() => setRows([]));
  useEffect(() => { load(); }, []);
  return (
    <div className="card">
      <h2>Seguridad</h2>
      <p className="small muted">Sus sesiones abiertas. Si no reconoce alguna, ciérrela y cambie su contraseña.
        Las sesiones se cierran solas tras 60 minutos sin actividad.</p>
      <SessionsTable rows={rows} onRevoke={async (s) => { await api(`/auth/sessions/${s.id}/revoke`, { method: "POST" }); load(); }} />
      {hasPassword && <div style={{ marginTop: 18 }}><PasswordChange /></div>}
    </div>
  );
}

interface Match { case_id: string; code: string; materia: string; status: string; organization: string; candidates: { id: string; username: string; full_name: string }[] }
interface Lookup { max_days: number; matches: Match[] }

function NewGrant({ onDone }: { onDone: () => void }) {
  const [code, setCode] = useState("");
  const [found, setFound] = useState<Lookup | null>(null);
  const [idx, setIdx] = useState(0);
  const [user, setUser] = useState("");
  const [reason, setReason] = useState("");
  const [expires, setExpires] = useState(() => toLocalInput(new Date(Date.now() + 7 * 864e5)));
  const [error, setError] = useState<string | null>(null);

  async function search(e: React.FormEvent) {
    e.preventDefault(); setError(null); setFound(null);
    try { setFound(await api<Lookup>(`/grants/lookup?code=${encodeURIComponent(code)}`)); setIdx(0); setUser(""); }
    catch (err) { setError(err instanceof ApiError ? err.message : "No encontrado."); }
  }
  async function create(e: React.FormEvent) {
    e.preventDefault(); setError(null);
    try {
      await api("/grants", { method: "POST", body: JSON.stringify({ user_id: user, case_id: found!.matches[idx].case_id, reason,
        expires_at: new Date(expires).toISOString() }) });
      setFound(null); setCode(""); setUser(""); setReason(""); onDone();
    } catch (err) { setError(err instanceof ApiError ? err.message : "No se pudo conceder."); }
  }
  return (
    <div className="card" style={{ background: "var(--surface-2)", marginBottom: 14 }}>
      <h3 style={{ marginTop: 0 }}>Conceder acceso temporal a un expediente</h3>
      {error && <div className="notice notice-danger" style={{ marginBottom: 10 }}>{error}</div>}
      <form className="row" onSubmit={search}>
        <input aria-label="Código de expediente" placeholder="Código, p. ej. LAB-2026-0001" value={code} onChange={(e) => setCode(e.target.value)} style={{ maxWidth: 260 }} required />
        <button className="btn btn-sm">Buscar</button>
      </form>
      {found && (
        <form className="form-grid" style={{ marginTop: 12 }} onSubmit={create}>
          {found.matches.length > 1 ? (
            <label className="field full">Ese código existe en varias entidades: elija cuál
              <select value={idx} onChange={(e) => { setIdx(Number(e.target.value)); setUser(""); }}>
                {found.matches.map((m, i) => <option key={m.case_id} value={i}>{m.code} · {m.organization}</option>)}
              </select>
            </label>
          ) : null}
          <p className="full small" style={{ margin: 0 }}>Expediente <strong className="mono">{found.matches[idx].code}</strong> · {found.matches[idx].organization} · {found.matches[idx].materia} · {found.matches[idx].status}</p>
          <label className="field">Persona
            <select value={user} onChange={(e) => setUser(e.target.value)} required>
              <option value="">Elija…</option>
              {found.matches[idx].candidates.map((c) => <option key={c.id} value={c.id}>{c.full_name} ({c.username})</option>)}
            </select>
          </label>
          <label className="field">Caduca (máximo {found.max_days} días)
            <input type="datetime-local" value={expires} onChange={(e) => setExpires(e.target.value)} required />
          </label>
          <label className="field full">Motivo (mínimo 10 caracteres; queda en la auditoría)
            <input value={reason} onChange={(e) => setReason(e.target.value)} minLength={10} required />
          </label>
          <div className="full"><button className="btn btn-primary">Conceder acceso</button></div>
        </form>
      )}
    </div>
  );
}

function Grants() {
  const [rows, setRows] = useState<Grant[] | null>(null);
  const load = () => api<Grant[]>("/grants").then(setRows).catch(() => setRows([]));
  useEffect(() => { load(); }, []);
  async function revoke(id: string) {
    await api(`/grants/${id}/revoke`, { method: "POST" });
    load();
  }
  return (
    <div className="card">
      <h2>Autorizaciones puntuales</h2>
      <p className="small muted">Accesos temporales y justificados a expedientes concretos (solo lectura). Caducan solos y pueden revocarse antes.</p>
      <NewGrant onDone={load} />
      <table className="data">
        <thead><tr><th>Usuario</th><th>Expediente</th><th>Motivo</th><th>Caduca</th><th>Estado</th><th></th></tr></thead>
        <tbody>
          {rows?.length === 0 && <tr><td colSpan={6} className="empty">No hay autorizaciones registradas.</td></tr>}
          {rows?.map((g) => {
            const vigente = !g.revoked_at && new Date(g.expires_at) > new Date();
            return (
              <tr key={g.id}>
                <td className="mono">{g.username}</td><td className="mono">{g.case_code}</td><td>{g.reason}</td>
                <td>{fmtDateTime(g.expires_at)}</td>
                <td>{vigente ? <span className="badge badge-green">Vigente</span> : <span className="badge">{g.revoked_at ? "Revocada" : "Caducada"}</span>}</td>
                <td>{vigente && <button className="btn btn-sm" onClick={() => revoke(g.id)}>Revocar</button>}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function Audit() {
  const [page, setPage] = useState(1);
  const [outcome, setOutcome] = useState("");
  const [data, setData] = useState<Page<AuditEvent> | null>(null);
  const [chain, setChain] = useState<{ integra: boolean; eventos_verificados: number } | null>(null);

  useEffect(() => {
    const qs = new URLSearchParams({ page: String(page), page_size: "25" });
    if (outcome) qs.set("outcome", outcome);
    api<Page<AuditEvent>>(`/audit-events?${qs}`).then(setData).catch(() => setData(null));
  }, [page, outcome]);

  return (
    <div className="card">
      <div className="row">
        <h2 style={{ margin: 0 }}>Auditoría</h2>
        <span className="spacer" />
        <select style={{ width: 200 }} value={outcome} onChange={(e) => { setOutcome(e.target.value); setPage(1); }} aria-label="Filtrar por resultado">
          <option value="">Todos los eventos</option><option value="denied">Solo denegaciones</option><option value="ok">Solo correctos</option>
        </select>
        <button className="btn btn-sm" onClick={() => api<{ integra: boolean; eventos_verificados: number }>("/audit-events/verify").then(setChain)}>Verificar integridad</button>
      </div>
      {chain && (
        <div className={`notice ${chain.integra ? "notice-ok" : "notice-danger"}`} style={{ margin: "12px 0" }}>
          {chain.integra ? `Cadena íntegra: ${chain.eventos_verificados} eventos verificados.` : "¡Atención! La cadena de auditoría presenta alteraciones."}
        </div>
      )}
      <table className="data" style={{ marginTop: 12 }}>
        <thead><tr><th>Fecha (Madrid)</th><th>Usuario</th><th>Acción</th><th>Recurso</th><th>Resultado</th></tr></thead>
        <tbody>
          {data?.items.map((e) => (
            <tr key={e.id}>
              <td>{fmtDateTime(e.occurred_at)}</td>
              <td className="mono">{e.actor_username ?? "sistema"}</td>
              <td>{label(ACCIONES_AUDITORIA, e.action)}{e.reason && <div className="small muted">{e.reason}</div>}</td>
              <td className="small mono">{e.resource_type}{e.resource_id ? ` · ${e.resource_id.slice(0, 8)}…` : ""}</td>
              <td>{e.outcome === "ok" ? <span className="badge badge-green">Correcto</span> : <span className="badge badge-red">Denegado</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {data && <Pager page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />}
    </div>
  );
}

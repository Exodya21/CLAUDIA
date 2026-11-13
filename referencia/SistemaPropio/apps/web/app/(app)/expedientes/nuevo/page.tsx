"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { useMe } from "@/components/session";
import { api, ApiError, fieldErrors, type CaseMeta, type Contact, type EligibleUser, type Organization, type Page } from "@/lib/api";
import { MATERIAS } from "@/lib/format";

function NuevoInner() {
  const me = useMe();
  const router = useRouter();
  const params = useSearchParams();
  const leadId = params.get("lead");
  const [orgs, setOrgs] = useState<Organization[]>([]);
  const [contact, setContact] = useState<{ id: string; name: string } | null>(null);
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Contact[] | null>(null);
  const [users, setUsers] = useState<EligibleUser[]>([]);
  const initialMateria = params.get("materia");
  const [f, setF] = useState({ organization_id: "", materia: initialMateria && initialMateria in MATERIAS ? initialMateria : "laboral", branch_id: "", title: "", summary: "", responsible_user_id: me.id });
  const [msg, setMsg] = useState<string | null>(null);
  const [errs, setErrs] = useState<Record<string, string>>({});

  useEffect(() => {
    api<Organization[]>("/organizations").then((o) => {
      const allowed = o.filter((x) => (me.permissions[x.id] ?? []).includes("case.create"));
      setOrgs(allowed);
      if (allowed[0]) setF((s) => ({ ...s, organization_id: allowed[0].id, branch_id: allowed[0].branches[0]?.id ?? "" }));
    });
    const c = params.get("contact");
    if (c) api<Contact>(`/contacts/${c}`).then((x) => setContact({ id: x.id, name: x.display_name })).catch(() => undefined);
  }, [me, params]);
  useEffect(() => {
    if (f.organization_id) api<EligibleUser[]>(`/cases/eligible-users?organization_id=${f.organization_id}&materia=${f.materia}`).then(setUsers).catch(() => setUsers([]));
  }, [f.organization_id, f.materia]);

  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setF((s) => ({ ...s, [k]: e.target.value }));
  const org = orgs.find((o) => o.id === f.organization_id);

  async function save() {
    setMsg(null); setErrs({});
    if (!contact) { setMsg("Elija el cliente."); return; }
    try {
      const c = await api<CaseMeta>("/cases", { method: "POST", body: JSON.stringify({ ...f, contact_id: contact.id, lead_id: leadId }) });
      router.push(`/expedientes/${c.id}?nuevo=1`);
    } catch (e) { setMsg(e instanceof ApiError ? e.message : "No se pudo abrir"); setErrs(fieldErrors(e)); }
  }

  if (!orgs.length) return <div className="notice notice-warn"><strong>Sin permiso</strong>Su rol no abre expedientes. <Link href="/expedientes">Volver</Link></div>;

  return (
    <div className="stack">
      <div className="topline">
        <div>
          <h1>Abrir expediente</h1>
          <p className="subtitle">Se crea en <strong>preapertura</strong> con un código consecutivo. Pasará a «abierto» cuando confirme que consta el encargo firmado.</p>
        </div>
        <Link className="btn" href={leadId ? `/crm/${leadId}` : "/expedientes"}>Cancelar</Link>
      </div>
      {leadId && <div className="notice notice-info">Se abrirá a partir de un lead: el lead quedará como <strong>convertido</strong> y enlazado a este expediente.</div>}
      {msg && <div className="notice notice-danger" role="alert">{msg}</div>}
      <fieldset>
        <legend>Cliente</legend>
        {contact ? <div className="row"><strong>{contact.name}</strong>{!leadId && <button className="btn btn-sm" onClick={() => setContact(null)}>Cambiar</button>}</div> : (
          <div className="stack" style={{ gap: 8 }}>
            <form className="search" onSubmit={async (e) => { e.preventDefault(); try { setResults((await api<Page<Contact>>(`/contacts?q=${encodeURIComponent(q)}&page_size=10`)).items); } catch (err) { setMsg(err instanceof ApiError ? err.message : "Error"); } }}>
              <input aria-label="Buscar cliente" placeholder="Nombre, teléfono o documento" value={q} onChange={(e) => setQ(e.target.value)} /><button className="btn" type="submit">Buscar</button>
            </form>
            {results?.map((c) => <button key={c.id} className="user-option" onClick={() => setContact({ id: c.id, name: c.display_name })}><strong>{c.display_name}</strong><span className="small muted">{c.primary_branch ?? "sin sede"}</span></button>)}
          </div>
        )}
      </fieldset>
      <fieldset>
        <legend>Expediente</legend>
        <div className="form-grid">
          {orgs.length > 1 && <label className="field">Entidad<select value={f.organization_id} onChange={set("organization_id")}>{orgs.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}</select></label>}
          <label className="field">Materia<select value={f.materia} onChange={set("materia")}>{Object.entries(MATERIAS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
          <label className="field">Sede<select value={f.branch_id} onChange={set("branch_id")}>{org?.branches.filter((b) => b.kind === "sede").map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}</select></label>
          <label className="field">Responsable<select value={f.responsible_user_id} onChange={set("responsible_user_id")} className={errs.responsible_user_id ? "invalid" : ""}>
            {users.map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}
            {!users.some((u) => u.id === me.id) && <option value={me.id}>Yo ({me.full_name})</option>}
          </select>{errs.responsible_user_id && <span className="error-text">{errs.responsible_user_id}</span>}</label>
          <label className="field full">Título *<input value={f.title} onChange={set("title")} placeholder="Ej.: Despido disciplinario, renovación de residencia…" className={errs.title ? "invalid" : ""} /></label>
          <label className="field full">Resumen confidencial<textarea rows={4} value={f.summary} onChange={set("summary")} /></label>
        </div>
      </fieldset>
      <div className="row"><button className="btn btn-primary" onClick={save}>Abrir expediente</button><span className="small muted">Solo puede abrir expedientes de su rama y su sede.</span></div>
    </div>
  );
}

export default function NuevoExpediente() {
  return <Suspense fallback={<p className="muted">Cargando…</p>}><NuevoInner /></Suspense>;
}

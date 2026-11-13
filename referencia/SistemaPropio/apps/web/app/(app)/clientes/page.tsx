"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { useMe } from "@/components/session";
import { AccessBadge, Pager } from "@/components/ui";
import { api, ApiError, hasPerm, type Contact, type Page } from "@/lib/api";

const PAGE_SIZE = 20;

function ClientesInner() {
  const me = useMe();
  const router = useRouter();
  const params = useSearchParams();
  const q = params.get("q") ?? "";
  const page = Number(params.get("page") ?? "1") || 1;
  const [term, setTerm] = useState(q);
  const [data, setData] = useState<Page<Contact> | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const canListAll = hasPerm(me, "contact.read.all") || hasPerm(me, "contact.read.own");

  const load = useCallback(async () => {
    setMsg(null);
    if (!q && !canListAll) { setData(null); return; }
    setLoading(true);
    try {
      const qs = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) });
      if (q) qs.set("q", q);
      setData(await api<Page<Contact>>(`/contacts?${qs}`));
    } catch (e) {
      setData(null);
      setMsg(e instanceof ApiError ? e.message : "No se pudo buscar.");
    } finally {
      setLoading(false);
    }
  }, [q, page, canListAll]);

  useEffect(() => { load(); }, [load]);

  function go(nq: string, np = 1) {
    const qs = new URLSearchParams();
    if (nq) qs.set("q", nq);
    if (np > 1) qs.set("page", String(np));
    router.push(`/clientes${qs.size ? `?${qs}` : ""}`);
  }

  return (
    <div className="stack">
      <div className="topline">
        <div>
          <h1>Clientes</h1>
          <p className="subtitle">Busque por nombre, teléfono o número de documento. Una persona = una ficha; puede tener varios expedientes.</p>
        </div>
        {hasPerm(me, "contact.create") && <Link className="btn btn-primary" href="/clientes/nuevo">+ Nuevo cliente</Link>}
      </div>

      <form className="search" role="search" onSubmit={(e) => { e.preventDefault(); go(term.trim()); }}>
        <input aria-label="Buscar cliente" placeholder="Ej.: Ferrer, 611000999, ZZDEMO00037…" value={term}
          onChange={(e) => setTerm(e.target.value)} />
        <button className="btn btn-primary" type="submit">Buscar</button>
      </form>

      {!canListAll && !q && (
        <div className="notice notice-info">
          <strong>Escriba al menos 3 caracteres</strong>
          Por protección de datos, su perfil no puede listar el directorio completo: solo localizar a una persona concreta.
        </div>
      )}
      {msg && <div className="notice notice-warn">{msg}</div>}
      {loading && <p className="muted">Buscando…</p>}

      {data && (
        <>
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr><th>Nombre</th><th>Teléfono</th><th>Documento</th><th>Sede</th><th>Acceso</th></tr>
              </thead>
              <tbody>
                {data.items.length === 0 && <tr><td colSpan={5} className="empty">Sin resultados para esta búsqueda.</td></tr>}
                {data.items.map((c) => (
                  <tr key={c.id} className="clickable" onClick={() => router.push(`/clientes/${c.id}`)}>
                    <td>
                      <Link href={`/clientes/${c.id}`} onClick={(e) => e.stopPropagation()}><strong>{c.display_name}</strong></Link>
                      {c.possible_duplicate && <> <span className="badge badge-yellow">Posible duplicado</span></>}
                    </td>
                    <td className="mono">{c.access_level === "full" && "points" in c
                      ? c.points.filter((p) => p.kind === "phone").map((p) => p.value_normalized).join(", ") || "—"
                      : c.phones_masked.join(", ") || "—"}</td>
                    <td className="mono">{c.access_level === "full" && "identifiers" in c
                      ? c.identifiers.map((i) => `${i.kind} ${i.number_normalized}`).join(", ") || "—"
                      : c.identifiers_masked.join(", ") || "—"}</td>
                    <td>{c.primary_branch ?? "—"}</td>
                    <td><AccessBadge level={c.access_level} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pager page={data.page} pageSize={data.page_size} total={data.total} onPage={(p) => go(q, p)} />
        </>
      )}
    </div>
  );
}

export default function ClientesPage() {
  return <Suspense fallback={<p className="muted">Cargando…</p>}><ClientesInner /></Suspense>;
}

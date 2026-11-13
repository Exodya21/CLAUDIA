"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useMe } from "@/components/session";
import { AccessBadge, EstadoBadge, MateriaBadge, Pager } from "@/components/ui";
import { api, hasPerm, type CaseMeta, type Page } from "@/lib/api";
import { FASES, fmtDateTime, MATERIAS } from "@/lib/format";

export default function Expedientes() {
  const me = useMe();
  const [materia, setMateria] = useState("");
  const [status, setStatus] = useState("");
  const [inactive, setInactive] = useState(false);
  const [mine, setMine] = useState(false);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Page<CaseMeta> | null>(null);

  useEffect(() => {
    const qs = new URLSearchParams({ page: String(page), page_size: "20" });
    if (materia) qs.set("materia", materia);
    if (status) qs.set("status", status);
    if (inactive) qs.set("inactive", "true");
    if (mine) qs.set("mine", "true");
    api<Page<CaseMeta>>(`/cases?${qs}`).then(setData).catch(() => setData(null));
  }, [materia, status, inactive, mine, page]);

  return (
    <div className="stack">
      <div className="topline">
        <div>
          <h1>Expedientes</h1>
          <p className="subtitle">Solo aparecen los expedientes que su perfil puede ver. Una persona puede tener varios, cada uno con su código.</p>
        </div>
        {hasPerm(me, "case.create") && <Link className="btn btn-primary" href="/expedientes/nuevo">+ Abrir expediente</Link>}
      </div>
      <div className="row">
        <label className="field" style={{ maxWidth: 260 }}>Materia
          <select value={materia} onChange={(e) => { setMateria(e.target.value); setPage(1); }}>
            <option value="">Todas las que puedo ver</option>
            {Object.entries(MATERIAS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label className="field" style={{ maxWidth: 220 }}>Fase
          <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
            <option value="">Todas</option>
            {Object.entries(FASES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label className="row small" style={{ marginTop: 20 }}><input type="checkbox" style={{ width: "auto" }} checked={mine} onChange={(e) => { setMine(e.target.checked); setPage(1); }} /> Asignados a mí</label>
        <label className="row small" style={{ marginTop: 20 }}><input type="checkbox" style={{ width: "auto" }} checked={inactive} onChange={(e) => { setInactive(e.target.checked); setPage(1); }} /> Sin actividad +30 días</label>
      </div>
      <div className="table-wrap">
        <table className="data">
          <thead><tr><th>Código</th><th>Materia</th><th>Cliente</th><th>Estado</th><th>Sede</th><th>Apertura</th><th>Acceso</th></tr></thead>
          <tbody>
            {!data && <tr><td colSpan={7} className="empty">Cargando…</td></tr>}
            {data?.items.length === 0 && <tr><td colSpan={7} className="empty">No hay expedientes visibles con este filtro.</td></tr>}
            {data?.items.map((x) => (
              <tr key={x.id}>
                <td className="mono">{x.access_level === "full" ? <Link href={`/expedientes/${x.id}`}>{x.code}</Link> : x.code}</td>
                <td><MateriaBadge materia={x.materia} /></td>
                <td>{x.contact_name ?? <Link href={`/clientes/${x.contact_id}`}>Ver identidad</Link>}</td>
                <td><EstadoBadge status={x.status} />{(x.inactive_days ?? 0) >= 30 && <div><span className="badge badge-red" style={{ marginTop: 4 }}>{x.inactive_days} días sin actividad</span></div>}</td>
                <td>{x.branch}</td>
                <td>{fmtDateTime(x.created_at)}</td>
                <td><AccessBadge level={x.access_level} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data && <Pager page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />}
    </div>
  );
}

"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { usePendingSummary } from "@/components/proposals";
import { useMe } from "@/components/session";
import { api, hasPerm, type Page, type Task } from "@/lib/api";
import { dayKey, MATERIAS } from "@/lib/format";

const PENDING_DEST: Record<string, { label: string; href: string }> = {
  conciliacion: { label: "Contabilidad · banco", href: "/contabilidad?tab=pendientes" },
  contabilidad: { label: "Contabilidad · facturas, remesas y cierre", href: "/contabilidad?tab=pendientes" },
  mensajes: { label: "Comunicaciones · mensajes por aprobar", href: "/comunicaciones?filtro=aprobar" },
  recepcion: { label: "Recepción · caja y cobros", href: "/recepcion?tab=pendientes" },
  rrhh: { label: "RRHH · avisos de plantilla", href: "/rrhh?tab=pendientes" },
};

export default function Inicio() {
  const me = useMe();
  const [cases, setCases] = useState<Record<string, number> | null>(null);
  const [contacts, setContacts] = useState<number | null>(null);
  const canListContacts = hasPerm(me, "contact.read.all") || hasPerm(me, "contact.read.own");
  const canLeads = hasPerm(me, "lead.read.all") || hasPerm(me, "lead.read.own");
  const [day, setDay] = useState<{ overdue: number; today: number; legal: number } | null>(null);
  const [followUp, setFollowUp] = useState<number | null>(null);

  useEffect(() => {
    api<Page<Task>>("/tasks?scope=mine&page_size=200").then((r) => {
      const today = dayKey(new Date().toISOString());
      setDay({
        overdue: r.items.filter((t) => t.overdue).length,
        today: r.items.filter((t) => !t.overdue && dayKey(t.start_at ?? t.due_at) === today).length,
        legal: r.items.filter((t) => t.legal_status === "pendiente_validacion").length,
      });
    }).catch(() => setDay(null));
    if (canLeads) api<Page<unknown>>("/leads?follow_up=true&page_size=1").then((r) => setFollowUp(r.total)).catch(() => undefined);
  }, [canLeads]);

  useEffect(() => {
    Promise.all(Object.keys(MATERIAS).map((m) =>
      api<Page<unknown>>(`/cases?page_size=1&materia=${m}`).then((r) => [m, r.total] as const),
    )).then((rows) => setCases(Object.fromEntries(rows))).catch(() => setCases({}));
    if (canListContacts) {
      api<Page<unknown>>("/contacts?page_size=1").then((r) => setContacts(r.total)).catch(() => setContacts(null));
    }
  }, [canListContacts]);

  const pending = usePendingSummary();
  const totalCases = cases ? Object.values(cases).reduce((a, b) => a + b, 0) : null;

  return (
    <div className="stack">
      <div className="topline">
        <div>
          <h1>Buenos días, {me.full_name.split(" (")[0]}</h1>
          <p className="subtitle">Esto es lo que su perfil puede consultar ahora mismo. Los recuentos salen de la base de datos.</p>
        </div>
      </div>

      <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
        <Link href="/agenda" className="card" style={{ color: "inherit", textDecoration: "none" }}>
          <div className="stat-label">Mi agenda de hoy</div>
          <div className="stat">{day ? day.today : "…"}</div>
          <div className="small muted">
            {day && day.overdue > 0 ? <span style={{ color: "var(--danger)", fontWeight: 600 }}>{day.overdue} vencida{day.overdue > 1 ? "s" : ""}</span> : "Sin tareas vencidas"}
            {day && day.legal > 0 && <> · {day.legal} plazo{day.legal > 1 ? "s" : ""} legal sin validar</>}
          </div>
        </Link>
        {canLeads ? (
          <Link href="/crm" className="card" style={{ color: "inherit", textDecoration: "none" }}>
            <div className="stat-label">Leads pendientes de seguimiento</div>
            <div className="stat">{followUp ?? "…"}</div>
            <div className="small muted">Más de 24 horas sin avanzar.</div>
          </Link>
        ) : <div className="card"><div className="stat-label">CRM</div><div className="stat">—</div><div className="small muted">Su rol no trabaja con leads.</div></div>}
        <div className="card">
          <div className="stat-label">Expedientes visibles para usted</div>
          <div className="stat">{totalCases ?? "…"}</div>
          {cases && <div className="small muted">
            {Object.entries(MATERIAS).map(([k, v]) => `${v}: ${cases[k] ?? 0}`).join(" · ")}
          </div>}
        </div>
        <div className="card">
          <div className="stat-label">{canListContacts ? "Clientes con ficha completa" : "Directorio de clientes"}</div>
          <div className="stat">{canListContacts ? (contacts ?? "…") : "Búsqueda"}</div>
          <div className="small muted">
            {canListContacts ? "Los demás aparecen como ficha mínima al buscar." : "Su perfil localiza identidades con datos enmascarados."}
          </div>
        </div>
      </div>

      {!!pending?.pending_total && (
        <div className="card" aria-label="Pendiente de decidir">
          <h2>Pendiente de decidir</h2>
          <p className="small muted" style={{ marginTop: 0 }}>Lo que los agentes han preparado y necesita a una persona. Cada cosa está en su sitio:</p>
          <div className="row">
            {Object.entries(pending.pending_by_agent).map(([agent, n]) => {
              const dest = PENDING_DEST[agent];
              return dest ? <Link key={agent} className="btn" href={dest.href}>{dest.label} <span className="count">{n}</span></Link> : null;
            })}
          </div>
        </div>
      )}

      <div className="grid grid-2">
        <div className="card">
          <h2>Sus ámbitos</h2>
          <table className="data">
            <thead><tr><th>Entidad</th><th>Sede</th><th>Departamento</th><th>Rol</th></tr></thead>
            <tbody>
              {me.memberships.map((m, i) => (
                <tr key={i}>
                  <td>{m.organization.name}</td>
                  <td>{m.branch ?? "Todas"}</td>
                  <td>{m.department ?? "—"}</td>
                  <td>{m.role_name}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card">
          <h2>Accesos rápidos</h2>
          <div className="stack" style={{ gap: 10 }}>
            {hasPerm(me, "contact.search") && <Link className="btn" href="/clientes">Buscar un cliente</Link>}
            {hasPerm(me, "contact.create") && <Link className="btn btn-primary" href="/clientes/nuevo">Dar de alta un cliente</Link>}
            <Link className="btn" href="/agenda">Ver mi agenda</Link>
            {canLeads && <Link className="btn" href="/crm">Abrir el CRM</Link>}
            <Link className="btn" href="/expedientes">Ver expedientes</Link>
            <Link className="btn" href="/ajustes">Mis permisos efectivos</Link>
          </div>
        </div>
      </div>
    </div>
  );
}

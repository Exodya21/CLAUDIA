"use client";

import { useCallback, useEffect, useState } from "react";
import { useMe } from "@/components/session";
import { NewTaskForm, TaskItem } from "@/components/tasks";
import { api, hasPerm, type Page, type Task } from "@/lib/api";
import { dayKey, fmtDay } from "@/lib/format";

function mondayOf(d: Date): Date {
  const x = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  x.setDate(x.getDate() - ((x.getDay() + 6) % 7));
  return x;
}
const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

export default function Agenda() {
  const me = useMe();
  const [monday, setMonday] = useState(() => mondayOf(new Date()));
  const [scope, setScope] = useState<"mine" | "all">("mine");
  const [week, setWeek] = useState<Task[] | null>(null);
  const [legal, setLegal] = useState<Task[]>([]);
  const [creating, setCreating] = useState(false);
  const canValidate = hasPerm(me, "deadline.validate");
  const orgId = me.memberships[0]?.organization.id;

  const load = useCallback(() => {
    api<{ items: Task[] }>(`/tasks/agenda/week?start=${iso(monday)}&scope=${scope}`).then((r) => setWeek(r.items)).catch(() => setWeek([]));
    if (canValidate) api<Page<Task>>("/tasks?scope=all&legal_pending=true&page_size=50").then((r) => setLegal(r.items.filter((t) => t.can_validate_legal))).catch(() => undefined);
  }, [monday, scope, canValidate]);
  useEffect(() => { load(); }, [load]);

  const days = Array.from({ length: 7 }, (_, i) => { const d = new Date(monday); d.setDate(d.getDate() + i); return d; });
  const firstKey = iso(days[0]);
  const overdue = (week ?? []).filter((t) => t.overdue && dayKey(t.start_at ?? t.due_at) < firstKey);
  const byDay = (d: Date) => (week ?? []).filter((t) => dayKey(t.start_at ?? t.due_at) === iso(d))
    .sort((a, b) => (a.start_at ?? a.due_at).localeCompare(b.start_at ?? b.due_at));
  const today = iso(new Date());

  return (
    <div className="stack">
      <div className="topline">
        <div>
          <h1>Agenda</h1>
          <p className="subtitle">Tareas, señalamientos y conciliaciones. La fecha interna del despacho y el plazo legal se muestran por separado; un plazo legal sin validar se ve en rojo.</p>
        </div>
        {hasPerm(me, "task.create") && <button className="btn btn-primary" onClick={() => setCreating(!creating)}>{creating ? "Cerrar" : "+ Tarea personal"}</button>}
      </div>
      {creating && orgId && <NewTaskForm orgId={orgId} meId={me.id} onCreated={() => { setCreating(false); load(); }} />}

      {legal.length > 0 && (
        <div className="notice notice-warn">
          <strong>{legal.length} plazo{legal.length > 1 ? "s" : ""} legal{legal.length > 1 ? "es" : ""} pendiente{legal.length > 1 ? "s" : ""} de su validación</strong>
          <div className="stack" style={{ gap: 8, marginTop: 8 }}>{legal.map((t) => <TaskItem key={t.id} task={t} onChange={load} />)}</div>
        </div>
      )}

      <div className="row">
        <button className="btn btn-sm" onClick={() => { const d = new Date(monday); d.setDate(d.getDate() - 7); setMonday(d); }}>← Semana anterior</button>
        <button className="btn btn-sm" onClick={() => setMonday(mondayOf(new Date()))}>Hoy</button>
        <button className="btn btn-sm" onClick={() => { const d = new Date(monday); d.setDate(d.getDate() + 7); setMonday(d); }}>Semana siguiente →</button>
        <strong style={{ marginLeft: 8 }}>Semana del {days[0].toLocaleDateString("es-ES")} al {days[6].toLocaleDateString("es-ES")}</strong>
        <span className="spacer" style={{ flex: 1 }} />
        <div className="tabs" role="tablist" style={{ border: 0 }}>
          <button role="tab" aria-selected={scope === "mine"} onClick={() => setScope("mine")}>Mis tareas</button>
          <button role="tab" aria-selected={scope === "all"} onClick={() => setScope("all")}>Todas las que puedo ver</button>
        </div>
      </div>

      {week === null && <p className="muted">Cargando…</p>}
      {overdue.length > 0 && (
        <section className="stack" style={{ gap: 8 }}>
          <h2 style={{ color: "var(--danger)", margin: 0 }}>Vencidas de semanas anteriores</h2>
          {overdue.map((t) => <TaskItem key={t.id} task={t} onChange={load} />)}
        </section>
      )}
      {week && days.map((d) => {
        const items = byDay(d);
        if (!items.length && iso(d) !== today) return null;
        return (
          <section key={iso(d)} className="stack" style={{ gap: 8 }}>
            <h2 style={{ margin: 0 }}>{cap(fmtDay(d.toISOString()))}{iso(d) === today && <span className="badge badge-blue" style={{ marginLeft: 8 }}>Hoy</span>}</h2>
            {items.length ? items.map((t) => <TaskItem key={t.id} task={t} onChange={load} />) : <p className="muted small">Nada previsto.</p>}
          </section>
        );
      })}
      {week && week.length === 0 && <div className="empty">No hay tareas esta semana.</div>}
    </div>
  );
}

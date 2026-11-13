"use client";

// Pendientes que preparan los agentes, mostrados DENTRO de cada departamento (Contabilidad, Comunicaciones,
// expediente, Recepción, RRHH). El servidor solo devuelve lo que la persona puede decidir.
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, type Proposal } from "@/lib/api";
import { TIPOS_PROPUESTA, fmtDateTime, label } from "@/lib/format";

const PRIO: Record<string, string> = { alta: "badge-red", media: "badge-yellow", baja: "" };

export interface PendingResult { items: Proposal[]; pending_by_agent: Record<string, number>; pending_total: number }

/** Lista de pendientes filtrada por función (agente, expediente o tipo). */
export function PendingList({ params, empty, onCount, decided = false, hideEmpty = false, title }: {
  params: Record<string, string>; empty?: string; onCount?: (n: number) => void; decided?: boolean;
  hideEmpty?: boolean; title?: string;
}) {
  const [status, setStatus] = useState<"pendiente" | "aprobada" | "rechazada">("pendiente");
  const [d, setD] = useState<Proposal[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const qs = new URLSearchParams({ ...params, status }).toString();
  // onCount suele ser una función nueva en cada render del padre: se guarda en una ref para no recargar en bucle
  const countRef = useRef(onCount);
  countRef.current = onCount;
  const load = useCallback(() => api<PendingResult>(`/proposals?${qs}`).then((r) => {
    setD(r.items); setErr(null); if (status === "pendiente") countRef.current?.(r.items.length);
  }).catch((e) => setErr(e instanceof ApiError ? e.message : "No disponible")), [qs, status]);
  useEffect(() => { load(); const t = setInterval(load, 30000); return () => clearInterval(t); }, [load]);
  if (hideEmpty && status === "pendiente" && (d === null || d.length === 0) && !err) return null;
  return (
    <div className="stack" style={{ gap: 10 }}>
      {title && <h2 style={{ margin: 0 }}>{title}</h2>}
      {decided && (
        <div className="segmented" role="radiogroup" aria-label="Estado de los pendientes">
          {(["pendiente", "aprobada", "rechazada"] as const).map((s) => (
            <button key={s} type="button" role="radio" aria-checked={status === s} onClick={() => setStatus(s)}>
              {s === "pendiente" ? "Por decidir" : s === "aprobada" ? "Aprobados" : "Rechazados"}
            </button>
          ))}
        </div>
      )}
      {err && <div className="notice notice-danger" role="alert">{err}</div>}
      {d === null && !err && <p className="muted">Cargando…</p>}
      {d?.length === 0 && <p className="muted">{status === "pendiente" ? (empty ?? "No hay nada pendiente.") : "Nada en esta vista."}</p>}
      {d?.map((p) => <ProposalCard key={p.id} p={p} onDone={load} />)}
    </div>
  );
}

/** Recuento de pendientes por agente (resumen de Inicio). */
export function usePendingSummary(): PendingResult | null {
  const [d, setD] = useState<PendingResult | null>(null);
  useEffect(() => { api<PendingResult>("/proposals?status=pendiente").then(setD).catch(() => setD(null)); }, []);
  return d;
}

const ACTIONS: Record<string, [string, string]> = {
  mensaje: ["Aprobar y enviar", "No enviar"],
  cobro_duplicado: ["Son cobros distintos", "Es repetido: anular"],
  cierre_caja: ["Validar cierre", "Rechazar: volver a contar"],
  aviso_rrhh: ["Crear tarea en mi agenda", "Descartar"],
  remesa_firma: ["Autorizar (mi firma)", "No autorizar"],
  cierre_mes: ["Preparar el borrador", "Descartar"],
  informe_revisar: ["Marcar como revisado", "Descartar aviso"],
};
const HINT: Record<string, string> = {
  dato_falta: "Complete el dato en la agenda del expediente; el mensaje se preparará solo.",
  invitar_portal: "Invite al cliente desde su ficha («Portal y mensajes»); este aviso se cerrará solo.",
  cierre_pendiente: "Cierre la caja en Recepción → Caja del día; este aviso se cerrará solo.",
  excepcion_banco: "Resuélvalo en el banco (conciliar a mano o registrar el cobro); se cerrará solo.",
  factura_validar: "Revísela en Contabilidad → Proveedores y facturas; el aviso se cerrará solo.",
  factura_vence: "Inclúyala en una remesa en Contabilidad → Tesorería; el aviso se cerrará solo.",
  factura_falta: "Pídala al proveedor y regístrela; el aviso se cerrará solo.",
};

export function ProposalCard({ p, onDone }: { p: Proposal; onDone: () => void }) {
  const [note, setNote] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function decide(approve: boolean) {
    if (!approve && note.trim().length < 5) { setErr("Indique el motivo (mín. 5 caracteres)."); return; }
    setBusy(true); setErr(null);
    try { await api(`/proposals/${p.id}/decide`, { method: "POST", body: JSON.stringify({ approve, note: note || null }) }); onDone(); }
    catch (e) { setErr(e instanceof ApiError ? e.message : "No se pudo decidir"); } finally { setBusy(false); }
  }
  const isMsg = p.kind === "mensaje";
  const [yes, no] = ACTIONS[p.kind] ?? ["Aprobar", "Rechazar"];
  return (
    <div className="card stack" style={{ gap: 8 }} aria-label={p.title}>
      <div className="row">
        <span className={`badge ${PRIO[p.priority] ?? ""}`}>{p.priority}</span>
        <span className="badge badge-blue">{p.agent_name}</span>
        <span className="badge">{label(TIPOS_PROPUESTA, p.kind)}</span>
        <strong>{p.title}</strong>
        <span className="spacer" />
        <span className="small muted">{fmtDateTime(p.created_at)}{p.assignee ? ` · para ${p.assignee}` : ""}</span>
      </div>
      {p.detail && (isMsg
        ? <blockquote className="comm-msg comm-out" style={{ margin: 0, whiteSpace: "pre-wrap" }}>{p.detail}</blockquote>
        : <p style={{ margin: 0, whiteSpace: "pre-wrap" }}>{p.detail}</p>)}
      {isMsg && p.payload && <p className="small muted" style={{ margin: 0 }}>Plantilla {String(p.payload.plantilla)} · versión {String(p.payload.version)} · se enviará por el portal del cliente (sin WhatsApp).</p>}
      <div className="row small">
        {p.case_code && p.case_id && <Link href={`/expedientes/${p.case_id}`}>Expediente {p.case_code}</Link>}
        {p.ref_type === "bank_movement" && p.ref_id && <Link href={`/contabilidad?mov=${p.ref_id}`}>Ver el movimiento</Link>}
        {(p.ref_type === "supplier_invoice" || p.ref_type === "supplier") && <Link href="/contabilidad?tab=facturas">Ver facturas</Link>}
        {p.ref_type === "payment_batch" && <Link href="/contabilidad?tab=tesoreria">Ver la remesa</Link>}
        {p.ref_type === "accounting_report" && <Link href="/contabilidad?tab=informes">Abrir el informe</Link>}
      </div>
      {p.status !== "pendiente" && (
        <p className="small muted" style={{ margin: 0 }}>{p.status === "aprobada" ? "Aprobada" : p.status === "rechazada" ? "Rechazada" : "Caducada"}{p.decided_by ? ` por ${p.decided_by}` : ""}{p.decided_at ? ` · ${fmtDateTime(p.decided_at)}` : ""}{p.decision_note ? ` · «${p.decision_note}»` : ""}</p>
      )}
      {err && <div className="notice notice-danger" role="alert">{err}</div>}
      {p.status === "pendiente" && (
        <div className="row">
          {!p.approvable && <p className="small muted" style={{ margin: 0, width: "100%" }}>{HINT[p.kind] ?? "Se resuelve en su pantalla; este aviso se cerrará solo."}</p>}
          <input aria-label="Nota de la decisión" value={note} onChange={(e) => setNote(e.target.value)} maxLength={500}
            placeholder={p.approvable ? "Nota (obligatoria si rechaza o hay diferencia)" : "Motivo para descartarlo"} style={{ flex: 1, minWidth: 220 }} />
          {p.approvable && <button className="btn btn-sm btn-primary" disabled={busy} onClick={() => decide(true)}>{yes}</button>}
          <button className="btn btn-sm" disabled={busy} onClick={() => decide(false)}>{p.approvable ? no : "Descartar"}</button>
        </div>
      )}
    </div>
  );
}

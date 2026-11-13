"""Agente de Recepción (DR-REC-4, DR-REC-8, DR-REC-10).

- Cierre de caja hecho → propuesta a un responsable (Contabilidad o Dirección) para validarlo; nunca quien contó.
- Cobro guardado pese a parecer repetido → Contabilidad lo revisa: «son distintos» o «es repetido» (se anula con
  motivo y, si era efectivo, se devuelve a la caja con su movimiento).
- A partir de las 20:00 de la sede, si hubo movimiento y nadie ha cerrado la caja → aviso a la recepción de esa sede.
"""

from __future__ import annotations

from datetime import time

from sqlalchemy import select

from ..models import Branch, CaseFile, Contact
from ..models_agents import AgentProposal
from ..models_economy import CashClosing, CashMovement, Payment
from ..reception import service as svc
from .base import Agent, ApplyError, RunContext, propose

CLOSE_REMINDER_FROM = time(20, 0)


class RecepcionAgent(Agent):
    code = "recepcion"
    name = "Recepción y caja"
    area = "Recepción"
    description = ("Pide la validación de cada cierre de caja, avisa si una sede no ha cerrado la caja del día y "
                   "pasa a Contabilidad los cobros que parecían repetidos.")
    covers = ("DR-REC-3", "DR-REC-4", "DR-REC-8", "DR-REC-9")
    requirements = ("Q-4.14", "Q-4.4", "I-101")
    events = ("cash.closed", "payment.duplicate_override")
    scheduled_every_min = 30
    can_be_automatic = False
    limits = ("No valida cierres ni anula cobros: lo decide un responsable.",
              "Los cálculos de caja son sumas de movimientos (deterministas), nunca estimaciones.",
              "No emite facturas: el justificante de Recepción no es fiscal.")

    def handle(self, ctx: RunContext, event) -> None:
        db = ctx.db
        if event.kind == "cash.closed":
            c = db.get(CashClosing, event.ref_id)
            if c is None or c.status != "pendiente_validacion":
                return
            b = db.get(Branch, c.branch_id)
            diff = c.difference_cents
            detail = (f"Esperado según movimientos {svc.eur(c.expected_cents, c.currency)}; contado "
                      f"{svc.eur(c.counted_cents, c.currency)}; diferencia {svc.eur(diff, c.currency)}."
                      + (f"\nMotivo indicado: {c.notes}" if c.notes else "")
                      + "\nValídelo solo después de comprobarlo; quien contó la caja no puede validarlo.")
            propose(ctx, self, kind="cierre_caja", title=f"Validar cierre de caja · {b.name} {c.day:%d/%m/%Y}",
                    permission="cash.close.validate", dedupe_key=f"cierre:{c.id}", priority="alta" if diff else "media",
                    detail=detail, branch_id=b.id, ref_type="cash_closing", ref_id=c.id,
                    payload={"diferencia_cents": diff, "sede": b.name, "dia": c.day.isoformat()})
            # El aviso de «falta el cierre» de ese día queda resuelto
            for p in db.execute(select(AgentProposal).where(
                    AgentProposal.dedupe_key == f"cierre_falta:{b.id}:{c.day.isoformat()}",
                    AgentProposal.status == "pendiente")).scalars():
                p.status, p.decided_at, p.decision_note = "caducada", svc.now(), "Caja cerrada."
        elif event.kind == "payment.duplicate_override":
            x = db.get(Payment, event.ref_id)
            if x is None or x.status == "anulado":
                return
            c = db.get(Contact, x.contact_id)
            cf = db.get(CaseFile, x.case_id) if x.case_id else None
            b = db.get(Branch, x.branch_id) if x.branch_id else None
            others = [db.get(Payment, i) for i in (event.payload or {}).get("parecidos", [])]
            lines = [f"Cobro nuevo: {svc.eur(x.amount_cents, x.currency)} · {svc.METHODS.get(x.method, x.method)} · "
                     f"{c.given_name} {c.family_names}" + (f" · {cf.code}" if cf else " · consulta"),
                     f"Motivo dado en Recepción: «{x.duplicate_reason}»", "Parecidos ya registrados:"]
            for o in others:
                if o is not None:
                    ocf = db.get(CaseFile, o.case_id) if o.case_id else None
                    lines.append(f"· {svc.eur(o.amount_cents, o.currency)} {svc.METHODS.get(o.method, o.method)} "
                                 f"{o.received_at.astimezone(svc.MADRID):%d/%m/%Y %H:%M} "
                                 f"{ocf.code if ocf else 'consulta'} ({o.status})")
            lines.append("Aprobar = son cobros distintos. Rechazar = es repetido: se anula con su motivo.")
            propose(ctx, self, kind="cobro_duplicado", title=f"¿Cobro repetido? {svc.eur(x.amount_cents, x.currency)} · "
                    f"{b.name if b else ''}", permission="payment.confirm", dedupe_key=f"dup:{x.id}", priority="alta",
                    detail="\n".join(lines), case_id=x.case_id, branch_id=x.branch_id, ref_type="payment", ref_id=x.id)

    def scheduled(self, ctx: RunContext) -> None:
        db = ctx.db
        for b in db.execute(select(Branch).where(Branch.organization_id == ctx.org_id, Branch.kind == "sede")).scalars():
            tz = svc.tz_for(b)
            local = svc.now().astimezone(tz)
            if local.time() < CLOSE_REMINDER_FROM:
                continue
            day = local.date()
            start, end = svc.day_bounds(day, tz)
            moved = db.execute(select(CashMovement.id).where(CashMovement.branch_id == b.id, CashMovement.at >= start,
                                                             CashMovement.at < end).limit(1)).first()
            if moved and svc.closing_of_day(db, b.id, day) is None:
                propose(ctx, self, kind="cierre_pendiente", title=f"Falta el cierre de caja de hoy · {b.name}",
                        permission="cash.operate", dedupe_key=f"cierre_falta:{b.id}:{day.isoformat()}", priority="alta",
                        detail="Hoy ha habido movimientos de caja y todavía no se ha contado ni cerrado. Cuente el "
                               "efectivo y ciérrela desde Recepción → Caja del día.", branch_id=b.id,
                        ref_type="branch", ref_id=b.id)

    def apply(self, db, proposal: AgentProposal, user, request_ctx) -> dict:
        try:
            if proposal.kind == "cierre_caja":
                c = db.get(CashClosing, proposal.ref_id)
                svc.decide_closing(db, c, user, True, proposal.decision_note, request_ctx)
                return {"cierre": str(c.id), "estado": c.status}
            if proposal.kind == "cobro_duplicado":
                return {"cobro": str(proposal.ref_id), "revision": "son cobros distintos"}
        except svc.ReceptionError as exc:
            raise ApplyError(exc.message, exc.status) from exc
        raise ApplyError("Se resuelve cerrando la caja en Recepción; el aviso se cerrará solo.", 422)

    def reject(self, db, proposal: AgentProposal, user) -> None:
        from ..routers.economy import annul

        try:
            if proposal.kind == "cierre_caja":
                c = db.get(CashClosing, proposal.ref_id)
                svc.decide_closing(db, c, user, False, proposal.decision_note, _Ctx())
            elif proposal.kind == "cobro_duplicado":
                x = db.get(Payment, proposal.ref_id)
                if x is not None and x.status != "anulado":
                    if not user.has(x.organization_id, "payment.confirm"):
                        raise ApplyError("Solo Contabilidad anula cobros.", 403)
                    try:
                        annul(db, x, user.id, f"Cobro repetido: {proposal.decision_note}", _Ctx())
                    except ValueError as exc:
                        raise ApplyError(str(exc), 422) from exc
        except svc.ReceptionError as exc:
            raise ApplyError(exc.message, exc.status) from exc


class _Ctx:
    ip = None
    request_id = None

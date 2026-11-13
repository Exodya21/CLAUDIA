"""Agente de Contabilidad (DR-CON-4, DR-CON-7, DR-CON-8).

- Facturas recibidas sin validar, que vencen en 7 días o que ya han vencido sin pagar → aviso a Contabilidad.
- Proveedor recurrente sin la factura del mes anterior (a partir del día 10) → aviso.
- Remesa propuesta → pide las DOS firmas, una a una, a quienes pueden autorizar (nunca a quien la propuso).
- A partir del día 5, si el mes anterior no tiene cierre provisional → propone prepararlo.
- Rutina de trabajo (F5.4b): crea los pasos del día, la semana, la quincena y el mes, con su tarea en la Agenda del
  responsable, y los da por hechos SOLO cuando lo comprueba en los datos. Genera los informes semanal (lunes),
  quincenal (días 1 y 16) y mensual (día 5), avisa sin cifras por correo y pide a Dirección que los revise.
No paga, no ordena transferencias, no valida facturas ni aprueba cierres: prepara y avisa.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select

from ..accounting import close as closing
from ..accounting import reports, routine
from ..models_accounting import MonthClose, PaymentBatch, PaymentBatchItem, Supplier, SupplierInvoice
from ..models_agents import AgentProposal
from .base import Agent, ApplyError, RunContext, propose

DUE_DAYS = 7
CLOSE_DAY = 5
RECURRING_DAY = 10


def _eur(c: int) -> str:
    return f"{c / 100:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


class ContabilidadAgent(Agent):
    code = "contabilidad"
    name = "Proveedores, tesorería y cierre"
    area = "Contabilidad"
    description = ("Vigila las facturas de proveedores (por validar, que vencen o vencidas, y las recurrentes que "
                   "faltan), pide las dos firmas de cada remesa y, el día 5, propone preparar el cierre provisional.")
    covers = ("DR-CON-4", "DR-CON-7", "DR-CON-8")
    requirements = ("Q-4.5", "Q-4.12", "I-074")
    events = ("treasury.batch.proposed",)
    scheduled_every_min = 60
    can_be_automatic = False
    limits = ("Nunca ordena transferencias ni paga: la remesa la autorizan dos personas y la sube al banco una persona.",
              "No valida facturas, no aprueba cierres y no aplica criterio fiscal (el IVA es el dato de la factura).",
              "No propone asientos hasta tener el plan de cuentas de la gestoría (T-40).")

    def handle(self, ctx: RunContext, event) -> None:
        b = ctx.db.get(PaymentBatch, event.ref_id)
        if b is not None and b.status == "propuesta":
            self._ask_signature(ctx.db, b, 1, ctx.run.id)

    def _ask_signature(self, db, b: PaymentBatch, n: int, run_id=None) -> None:
        key = f"remesa:{b.id}:{n}"
        if db.execute(select(AgentProposal.id).where(AgentProposal.dedupe_key == key)).first():
            return
        items = list(db.execute(select(PaymentBatchItem).where(PaymentBatchItem.batch_id == b.id)).scalars())
        lines = []
        for it in items:
            inv = db.get(SupplierInvoice, it.invoice_id)
            sup = db.get(Supplier, inv.supplier_id)
            lines.append(f"· {sup.name} · factura {inv.number} · {_eur(it.amount_cents)}"
                         + (f" · vence {inv.due_date:%d/%m/%Y}" if inv.due_date else ""))
        db.add(AgentProposal(
            organization_id=b.organization_id, agent_code=self.code, kind="remesa_firma",
            title=f"Firma {n} de 2 · remesa {b.code} · {_eur(b.total_cents)}", priority="alta",
            detail=f"Pago a proveedores el {b.execution_date:%d/%m/%Y} ({len(items)} factura(s)):\n" + "\n".join(lines)
                   + "\nHacen falta dos personas distintas de quien la propone. Autorizar no envía nada al banco.",
            permission="treasury.approve", ref_type="payment_batch", ref_id=b.id, dedupe_key=key, run_id=run_id,
            payload={"remesa": b.code, "firma": n}))

    def scheduled(self, ctx: RunContext) -> None:
        db = ctx.db
        today = date.today()
        if routine.users_with(db, ctx.org_id, "accounting.read"):
            routine.sync(db, ctx.org_id, today)
            for r in reports.ensure_due(db, ctx.org_id, today):
                self._ask_review(ctx, r)
        for inv in db.execute(select(SupplierInvoice).where(SupplierInvoice.organization_id == ctx.org_id,
                                                            SupplierInvoice.status.in_(("recibida", "validada")))).scalars():
            sup = db.get(Supplier, inv.supplier_id)
            head = f"{sup.name} · {inv.number} · {_eur(inv.total_cents)}"
            if inv.status == "recibida" and inv.registered_at.date() <= today - timedelta(days=2):
                propose(ctx, self, kind="factura_validar", title=f"Validar factura · {head}", permission="invoice.validate",
                        dedupe_key=f"fval:{inv.id}", priority="media", ref_type="supplier_invoice", ref_id=inv.id,
                        detail="Factura registrada hace más de dos días sin validar: revise datos, actividad y oficina.")
            if inv.status == "validada" and inv.due_date:
                in_batch = db.execute(select(PaymentBatchItem.id).join(PaymentBatch, PaymentBatch.id == PaymentBatchItem.batch_id)
                                      .where(PaymentBatchItem.invoice_id == inv.id,
                                             PaymentBatch.status.in_(("propuesta", "autorizada", "enviada")))).first()
                if in_batch:
                    continue
                if inv.due_date < today:
                    propose(ctx, self, kind="factura_vence", title=f"Factura vencida sin pagar · {head}",
                            permission="treasury.propose", dedupe_key=f"fvencida:{inv.id}", priority="alta",
                            ref_type="supplier_invoice", ref_id=inv.id,
                            detail=f"Venció el {inv.due_date:%d/%m/%Y}. Inclúyala en una remesa o confirme con el proveedor.")
                elif inv.due_date <= today + timedelta(days=DUE_DAYS):
                    propose(ctx, self, kind="factura_vence", title=f"Vence pronto · {head}", permission="treasury.propose",
                            dedupe_key=f"fvence:{inv.id}", priority="media", ref_type="supplier_invoice", ref_id=inv.id,
                            detail=f"Vence el {inv.due_date:%d/%m/%Y}. Inclúyala en la próxima remesa.")
        if today.day >= RECURRING_DAY:
            prev_first = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
            for sup in db.execute(select(Supplier).where(Supplier.organization_id == ctx.org_id, Supplier.recurring,
                                                         Supplier.active)).scalars():
                has = db.execute(select(SupplierInvoice.id).where(
                    SupplierInvoice.supplier_id == sup.id, SupplierInvoice.status != "rechazada",
                    SupplierInvoice.issue_date >= prev_first, SupplierInvoice.issue_date < today.replace(day=1))).first()
                if not has:
                    propose(ctx, self, kind="factura_falta", title=f"Falta la factura de {prev_first:%m/%Y} · {sup.name}",
                            permission="invoice.register", dedupe_key=f"ffalta:{sup.id}:{prev_first:%Y-%m}",
                            priority="media", ref_type="supplier", ref_id=sup.id,
                            detail="Es un proveedor de factura mensual y no consta la del mes pasado. Pídala y regístrela.")
        if today.day >= CLOSE_DAY:
            month = closing.prev_month(f"{today:%Y-%m}")
            exists = db.execute(select(MonthClose.id).where(MonthClose.organization_id == ctx.org_id, MonthClose.month == month,
                                                            MonthClose.status != "sustituido")).first()
            if not exists:
                propose(ctx, self, kind="cierre_mes", title=f"Preparar el cierre provisional de {month}",
                        permission="accounting.close", dedupe_key=f"cierre:{ctx.org_id}:{month}", priority="alta",
                        ref_type="month_close_due", ref_id=ctx.org_id, payload={"mes": month},
                        detail="Es día 5 o posterior. Aprobar prepara el borrador con las cifras por actividad y oficina, "
                               "los pendientes y la fiabilidad; después lo revisa Contabilidad y lo aprueba Dirección.")

    def _ask_review(self, ctx: RunContext, r) -> None:
        propose(ctx, self, kind="informe_revisar", title=f"{reports.KIND_LABEL[r.kind]} listo · {r.label}",
                permission="accounting.close.approve", dedupe_key=f"informe:{r.id}", priority="media",
                ref_type="accounting_report", ref_id=r.id, payload={"tipo": r.kind},
                detail="Léalo en Contabilidad → Informes (pantalla, PDF o CSV). Aprobar lo marca como revisado; "
                       "la rutina lo da por hecho.")

    def apply(self, db, proposal: AgentProposal, user, request_ctx) -> dict:
        from ..routers.accounting import prepare_close, review_report, sign_batch

        if proposal.kind == "informe_revisar":
            from ..models_accounting import AccountingReport
            r = db.get(AccountingReport, proposal.ref_id)
            try:
                review_report(db, r, user, proposal.decision_note, request_ctx)
            except ValueError as exc:
                raise ApplyError(str(exc), 409) from exc
            return {"informe": r.label, "revisado": True}

        if proposal.kind == "remesa_firma":
            b = db.get(PaymentBatch, proposal.ref_id)
            try:
                sign_batch(db, b, user, True, proposal.decision_note, request_ctx)
            except PermissionError as exc:
                raise ApplyError(str(exc), 403) from exc
            except ValueError as exc:
                raise ApplyError(str(exc), 409) from exc
            if b.status == "propuesta":
                self._ask_signature(db, b, 2)
            return {"remesa": b.code, "estado": b.status}
        if proposal.kind == "cierre_mes":
            try:
                c = prepare_close(db, proposal.organization_id, (proposal.payload or {})["mes"], user.id, None, request_ctx)
            except ValueError as exc:
                raise ApplyError(str(exc), 409) from exc
            return {"cierre": str(c.id), "revision": c.revision}
        raise ApplyError("Se resuelve en Contabilidad (registrar, validar o incluir en una remesa); el aviso se cerrará solo.", 422)

    def reject(self, db, proposal: AgentProposal, user) -> None:
        from ..routers.accounting import sign_batch

        if proposal.kind == "remesa_firma":
            b = db.get(PaymentBatch, proposal.ref_id)
            try:
                sign_batch(db, b, user, False, proposal.decision_note, _Ctx())
            except PermissionError as exc:
                raise ApplyError(str(exc), 403) from exc
            except ValueError as exc:
                raise ApplyError(str(exc), 422) from exc


class _Ctx:
    ip = None
    request_id = None

"""Agente de conciliación bancaria (DR-CON-2, DR-CON-3; Q-4.5).

- Tras cada importación (evento `bank.imported`) y cada hora (por si se registran cobros después) revisa los
  movimientos sin conciliar con las reglas deterministas de `bank/matcher.py`.
- Deja en la bandeja una propuesta de emparejamiento (con su explicación) o una excepción con categoría sugerida.
- NUNCA concilia solo: Contabilidad valida. Validar confirma los cobros emparejados (como «Confirmar cobro»).
"""

from __future__ import annotations

import hashlib

from sqlalchemy import select

from ..bank import matcher, service
from ..models_agents import AgentProposal
from ..models_bank import BankAccount, BankMatch, BankMovement
from .base import Agent, ApplyError, RunContext, propose

PERM = "bank.reconcile"


NOT_BY_CATEGORY = ("cobro", "traspaso", "tpv", "bizum", "devolucion")


def exception_approvable(category: str | None, amount_cents: int) -> bool:
    """Solo un CARGO con categoría clara (comisión, seguro social, impuestos…) se justifica aprobando la excepción.
    Ingresos, traspasos, TPV, Bizum y devoluciones se concilian con lo que los justifica."""
    return bool(category) and category not in NOT_BY_CATEGORY and amount_cents < 0


class ConciliacionAgent(Agent):
    code = "conciliacion"
    name = "Conciliación bancaria"
    area = "Contabilidad"
    description = ("Empareja cada movimiento del banco con su cobro, devolución, liquidación de TPV, comisión o "
                   "traspaso entre cuentas, y explica por qué. Lo que no cuadra va a la bandeja como excepción.")
    covers = ("DR-CON-2", "DR-CON-3")
    requirements = ("Q-4.5", "I-074", "I-075")
    events = ("bank.imported",)
    scheduled_every_min = 60
    can_be_automatic = False
    limits = ("No valida ni concilia nada por su cuenta: propone y explica.",
              "No calcula honorarios, IVA ni comisiones: solo compara importes que ya existen.",
              "Un traspaso entre cuentas propias nunca se trata como ingreso.",
              "No emite facturas ni toca la contabilidad oficial (gestoría, T-40).")

    def handle(self, ctx: RunContext, event) -> None:
        rows = ctx.db.execute(select(BankMovement).where(BankMovement.import_id == event.ref_id,
                                                         BankMovement.status == "pendiente")
                              .order_by(BankMovement.booking_date, BankMovement.id)).scalars()
        for m in list(rows):
            self.review(ctx, m)

    def scheduled(self, ctx: RunContext) -> None:
        rows = ctx.db.execute(select(BankMovement).where(BankMovement.organization_id == ctx.org_id,
                                                         BankMovement.status.in_(("pendiente", "sin_justificar")))
                              .order_by(BankMovement.booking_date, BankMovement.id).limit(2000)).scalars()
        for m in list(rows):
            self.review(ctx, m)

    def review(self, ctx: RunContext, m: BankMovement) -> None:
        db = ctx.db
        if m.status not in ("pendiente", "sin_justificar"):
            return
        ctx.count("revisados")
        r = matcher.evaluate(db, m)
        acc = db.get(BankAccount, m.account_id)
        head = f"{m.booking_date:%d/%m/%Y} · {matcher.eur(m.amount_cents)} · {acc.name}"
        if isinstance(r, matcher.Candidate):
            sig = hashlib.sha256("|".join(sorted(f"{t.type}:{t.id}" for t in r.targets)).encode()).hexdigest()[:16]
            # Las propuestas de emparejamiento se crean juntas con su BankMatch (punto de guardado propio).
            with db.begin_nested():
                p = propose(ctx, self, kind="conciliacion", title=f"Conciliar {head}", permission=PERM,
                            dedupe_key=f"conc:{m.id}:{sig}", priority="media" if r.rule != "importe_fecha" else "alta",
                            detail="\n".join([r.explanation, *r.warnings]), case_id=r.case_id,
                            ref_type="bank_movement", ref_id=m.id,
                            payload={"regla": r.rule, "movimiento": m.description[:120]})
                if p is None:
                    # Ya se propuso (y quizá se rechazó): no insistir; dejar constancia como excepción.
                    self._exception(ctx, m, head, matcher.Exception_(
                        "propuesta_ya_revisada", "La única coincidencia encontrada ya se revisó antes. Concilie a mano "
                        "o justifique el movimiento.", matcher.suggest_category(m)))
                    return
                ids = []
                for t in r.targets:
                    bm = BankMatch(organization_id=m.organization_id, movement_id=m.id, target_type=t.type,
                                   target_id=t.id, amount_cents=t.amount_cents, rule=r.rule,
                                   explanation=r.explanation, proposed_by_agent=self.code)
                    db.add(bm)
                    db.flush()
                    ids.append(str(bm.id))
                p.payload = {**(p.payload or {}), "match_ids": ids}
                if m.status == "sin_justificar":
                    service._close_open_proposals(db, m, None, "hay una coincidencia nueva")
                m.status = "propuesto"
                m.category = m.category or ("traspaso" if r.rule == "traspaso" else None)
            ctx.count(f"regla_{r.rule}")
        else:
            self._exception(ctx, m, head, r)

    def _exception(self, ctx: RunContext, m: BankMovement, head: str, e: matcher.Exception_) -> None:
        p = propose(ctx, self, kind="excepcion_banco", title=f"Revisar {head}", permission=PERM,
                    dedupe_key=f"exc:{m.id}:{e.reason}", priority=e.priority, detail=e.detail, case_id=e.case_id,
                    ref_type="bank_movement", ref_id=m.id,
                    payload={"motivo": e.reason, "categoria_sugerida": e.category, "movimiento": m.description[:120],
                             "importe": m.amount_cents, "aprobable": exception_approvable(e.category, m.amount_cents)})
        if m.status == "pendiente":
            m.status = "sin_justificar"
        if p is not None:
            ctx.count("excepciones")

    # ------------------------------------------------------------ decisiones de la bandeja
    def apply(self, db, proposal: AgentProposal, user, request_ctx) -> dict:
        m = db.get(BankMovement, proposal.ref_id)
        if m is None:
            raise ApplyError("El movimiento ya no existe.", 404)
        try:
            if proposal.kind == "conciliacion":
                ids = (proposal.payload or {}).get("match_ids") or []
                matches = [db.get(BankMatch, i) for i in ids]
                if not matches or any(x is None or x.movement_id != m.id for x in matches):
                    raise ApplyError("La propuesta no tiene emparejamientos válidos.")
                return service.validate_matches(db, m, matches, user, request_ctx, proposal.decision_note)
            if proposal.kind == "excepcion_banco":
                cat = (proposal.payload or {}).get("categoria_sugerida")
                if not exception_approvable(cat, m.amount_cents):
                    raise ApplyError("Esta excepción no se resuelve aprobándola: concilie el movimiento a mano en "
                                     "Banco (o registre el cobro) y la propuesta se cerrará sola.", 422)
                return service.justify(db, m, cat, user, request_ctx,
                                       f"Justificado desde la bandeja como «{cat}» (propuesta del agente).")
        except service.BankError as exc:
            raise ApplyError(exc.message, exc.status) from exc
        raise ApplyError("Tipo de propuesta desconocido.")

    def reject(self, db, proposal: AgentProposal, user) -> None:
        if proposal.kind != "conciliacion":
            return
        m = db.get(BankMovement, proposal.ref_id)
        ids = (proposal.payload or {}).get("match_ids") or []
        matches = [x for x in (db.get(BankMatch, i) for i in ids) if x is not None]
        if m is not None:
            service.reject_matches(db, m, matches, user.id, proposal.decision_note)

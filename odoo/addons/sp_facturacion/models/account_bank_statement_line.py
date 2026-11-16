"""Conciliación por número de expediente (AL-12, 16/11/2026): el sistema propone y prepara la factura; Contabilidad
valida con un clic y entonces se emite (Verifactu) y se concilia."""
import re

from odoo import Command, _, fields, models
from odoo.exceptions import UserError

from odoo.addons.sp_banco.models.account_bank_statement_line import eur


class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    sp_expediente_id = fields.Many2one("sp.expediente", "Expediente", readonly=True, index="btree_not_null")
    sp_factura_expediente_id = fields.Many2one("account.move", "Factura emitida al validar", readonly=True)

    def _sp_reglas(self):
        reglas = super()._sp_reglas()
        reglas.insert(1, self._sp_regla_expediente)  # justo después del traspaso entre cuentas propias
        return reglas

    def _sp_valores_reinicio(self):
        return {**super()._sp_valores_reinicio(), "sp_expediente_id": False}

    def _sp_regla_expediente(self):
        if self.amount <= 0:
            return None
        texto = f"{self.payment_ref or ''} {self.sp_referencia or ''}"
        # La Norma 43 trocea el concepto en tramos de 38 caracteres: se busca también sin espacios entre cifras.
        texto += " " + re.sub(r"(?<=[\dA-Z\-])\s+(?=[\d\-])", "", texto.upper())
        numeros, expedientes = self.env["sp.expediente"]._sp_buscar_en_texto(texto, self.company_id)
        if not numeros:
            return None
        if not expedientes:
            return ("excepcion", "expediente_no_existe",
                    _("El concepto trae %(n)s, pero no existe ese expediente en %(c)s. Revise el número con el cliente.",
                      n=", ".join(numeros), c=self.company_id.name), {"prioridad": "alta"})
        if len(expedientes) > 1:
            return ("excepcion", "expediente_ambiguo",
                    _("El concepto trae varios expedientes (%s). Reparta el pago a mano.", ", ".join(expedientes.mapped("name"))),
                    {"prioridad": "alta"})
        e = expedientes
        vals = {"vals": {"sp_expediente_id": e.id}}
        if not e.sale_order_id:
            return ("excepcion", "expediente_sin_honorarios",
                    _("Pago de %(i)s para %(n)s (%(c)s), pero el expediente no tiene honorarios fijados. Fíjelos y "
                      "vuelva a proponer.", i=eur(self.amount), n=e.name, c=e.partner_id.name),
                    {**vals, "prioridad": "alta"})
        otros = self.search([("id", "!=", self.id), ("sp_expediente_id", "=", e.id), ("sp_estado", "=", "propuesto"),
                             ("sp_regla", "=", "expediente")])
        comprometido = sum(otros.mapped("amount"))
        disponible = e.currency_id.round(e.sp_pendiente - comprometido)
        if self.amount > disponible + 0.001:
            return ("excepcion", "expediente_pago_excesivo",
                    _("Pago de %(i)s para %(n)s, pero solo quedan %(d)s por pagar%(o)s. Revise si es de otro expediente o "
                      "si hay que devolver la diferencia.", i=eur(self.amount), n=e.name, d=eur(disponible),
                      o=_(" (hay otros %s pagos propuestos)", len(otros)) if otros else ""), {**vals, "prioridad": "alta"})
        pedido = e.sale_order_id.sudo()
        factor = pedido.amount_total / pedido.amount_untaxed if pedido.amount_untaxed else 1.0
        base = self.amount / factor
        desglose = _("base %(b)s + IVA %(v)s", b=eur(base), v=eur(base * 0.21))
        if e.sp_retencion:
            desglose += _(" − retención IRPF %s", eur(base * 0.15))
        queda = e.currency_id.round(disponible - self.amount)
        if e.currency_id.is_zero(queda):
            if not e._sp_facturas_emitidas() and not otros:
                que = _("Al validar se emite UNA factura por todo el expediente (%s) y se concilia.", desglose)
            else:
                que = _("Al validar se emite la factura de anticipo (%s) y, como el expediente queda pagado, la factura "
                        "final con los honorarios y los anticipos descontados (total 0 €).", desglose)
        else:
            que = _("Al validar se emite una factura de anticipo (%(d)s) y se concilia. Quedarán %(q)s por pagar.",
                    d=desglose, q=eur(queda))
        return ("propuesto", "expediente",
                _("Pago de %(i)s para el expediente %(n)s de %(c)s (pactado %(t)s, pendiente %(p)s). %(que)s",
                  i=eur(self.amount), n=e.name, c=e.partner_id.name, t=eur(e.sp_total_pactado), p=eur(disponible),
                  que=que), vals)

    def action_sp_validar(self):
        self._sp_exigir()
        por_expediente = self.filtered(lambda s: s.sp_estado == "propuesto" and s.sp_regla == "expediente")
        for st in por_expediente:
            e = st.sp_expediente_id
            if not e:
                raise UserError(_("La propuesta no tiene expediente. Vuelva a proponer."))
            factura = e._sp_facturar_pago(st.amount, st.date)
            cobro = factura.line_ids.filtered(lambda l: l.account_id.account_type == "asset_receivable")
            st.sudo().write({"sp_propuesta_aml_ids": [Command.set(cobro.ids)], "sp_factura_expediente_id": factura.id})
        res = super().action_sp_validar()
        for st in por_expediente:
            st.sp_expediente_id._sp_factura_final(st.date)
            st.sp_expediente_id.message_post(body=_("Pago de %(i)s del %(f)s conciliado con la factura %(n)s.",
                                                    i=eur(st.amount), f=st.date.strftime("%d/%m/%Y"),
                                                    n=st.sp_factura_expediente_id.name))
        return res

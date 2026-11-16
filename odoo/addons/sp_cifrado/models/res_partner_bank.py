from odoo import _, api, models

from .. import cifrado
from .campo import CharCifrado

OPERADORES_TROZO = ("like", "ilike", "not like", "not ilike", "=like", "=ilike")


class ResPartnerBank(models.Model):
    _inherit = "res.partner.bank"

    # Cifrados en la base de datos. Sin seguimiento automático (guardaría el IBAN completo en el historial): el cambio
    # se anota enmascarado en el chatter de la empresa.
    account_number = CharCifrado("Account Number", required=True, search="_search_account_number", tracking=False)
    sanitized_account_number = CharCifrado(compute="_compute_sanitized_account_number", string="Sanitized Account Number",
                                           readonly=True, store=True)

    def _search_account_number(self, operator, value):
        if operator in OPERADORES_TROZO and isinstance(value, str):
            # La base de datos no puede buscar trozos de un texto cifrado: se descifra en memoria (hay pocas cuentas).
            from odoo.addons.base.models.res_partner_bank import sanitize_account_number
            trozo = sanitize_account_number(value.replace("%", "")) or ""
            todas = self.sudo().with_context(active_test=False).search_fetch([], ["sanitized_account_number"])
            ids = [b.id for b in todas if trozo in (b.sanitized_account_number or "")]
            return [("id", "not in" if operator.startswith("not") else "in", ids)]
        return super()._search_account_number(operator, value)

    @api.model_create_multi
    def create(self, vals_list):
        cuentas = super().create(vals_list)
        for c in cuentas:
            c.partner_id.sudo().message_post(body=_("Cuenta bancaria añadida: %s", cifrado.enmascarar(c.account_number)))
        return cuentas

    def write(self, vals):
        antes = {c.id: c.account_number for c in self} if "account_number" in vals else {}
        res = super().write(vals)
        for c in self.filtered(lambda c: c.id in antes and antes[c.id] != c.account_number):
            c.partner_id.sudo().message_post(body=_("Cuenta bancaria cambiada: %(a)s → %(n)s",
                                                    a=cifrado.enmascarar(antes[c.id]),
                                                    n=cifrado.enmascarar(c.account_number)))
        return res

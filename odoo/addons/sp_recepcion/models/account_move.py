from odoo import _, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    def _sp_en_caja_cerrada(self):
        """Apuntes ya publicados en la caja de una sede con fecha de un día cuya caja está validada."""
        cerrados = self.env["account.move"]
        Cierre = self.env["sp.cierre.caja"].sudo()
        for move in self.filtered(lambda m: m.state == "posted" and m.journal_id.type == "cash"):
            if Cierre.search_count([("journal_id", "=", move.journal_id.id), ("estado", "=", "validado"),
                                    ("fecha", ">=", move.date)], limit=1):
                cerrados |= move
        return cerrados

    def button_draft(self):
        cerrados = self._sp_en_caja_cerrada()
        if cerrados:
            raise UserError(_("La caja de ese día ya está validada: %(m)s no puede volver a borrador. Registre el "
                              "movimiento contrario con fecha de hoy.", m=", ".join(cerrados.mapped("name"))))
        return super().button_draft()

    def button_cancel(self):
        cerrados = self._sp_en_caja_cerrada()
        if cerrados:
            raise UserError(_("La caja de ese día ya está validada: %(m)s no se puede cancelar.",
                              m=", ".join(cerrados.mapped("name"))))
        return super().button_cancel()

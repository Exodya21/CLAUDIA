from odoo import fields, models


class SpAnularCobro(models.TransientModel):
    _name = "sp.anular.cobro"
    _description = "Anular cobro de recepción (con motivo)"

    payment_ids = fields.Many2many("account.payment", string="Cobros", required=True,
                                   default=lambda s: s.env.context.get("active_ids"))
    motivo = fields.Text("Motivo de la anulación", required=True)

    def action_anular(self):
        self.payment_ids._sp_anular(self.motivo)
        return {"type": "ir.actions.act_window_close"}

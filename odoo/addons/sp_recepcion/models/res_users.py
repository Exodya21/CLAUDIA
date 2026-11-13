from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    sp_sede_id = fields.Many2one("sp.sede", "Sede habitual",
                                 help="Sede que se propone al registrar un cobro o un cierre de caja.")
    sp_sede_ids = fields.Many2many(
        "sp.sede", "sp_sede_res_users_rel", "user_id", "sede_id", string="Sedes en las que trabaja",
        help="Una persona de Recepción solo ve y registra cobros y cierres de caja de estas sedes (y de su sede "
             "habitual). Contabilidad las ve todas.")

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        users._sp_incluir_sede_habitual()
        return users

    def write(self, vals):
        res = super().write(vals)
        if "sp_sede_id" in vals or "sp_sede_ids" in vals:
            self._sp_incluir_sede_habitual()
        return res

    def _sp_incluir_sede_habitual(self):
        for u in self:
            if u.sp_sede_id and u.sp_sede_id not in u.sp_sede_ids:
                u.sudo().sp_sede_ids = [(4, u.sp_sede_id.id)]

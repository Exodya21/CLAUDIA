from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    sp_sede_id = fields.Many2one("sp.sede", "Sede habitual", help="Sede que se propone al registrar un cobro de recepción.")

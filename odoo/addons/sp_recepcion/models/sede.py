from odoo import api, fields, models


class SpSede(models.Model):
    _name = "sp.sede"
    _description = "Sede del despacho"
    _order = "sequence, name"

    name = fields.Char("Sede", required=True)
    code = fields.Char("Código", required=True, size=5, help="Se usa en el número del justificante: REC-<código>-año-nº")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", "Compañía", required=True, default=lambda s: s.env.company)
    journal_id = fields.Many2one(
        "account.journal", "Caja (diario de efectivo)", required=True,
        domain="[('type', '=', 'cash'), ('company_id', '=', company_id)]")
    receipt_sequence_id = fields.Many2one("ir.sequence", "Numeración de justificantes", readonly=True, copy=False)

    _code_company_uniq = models.Constraint("unique(code, company_id)", "Ya hay una sede con ese código en la compañía.")

    @api.model_create_multi
    def create(self, vals_list):
        sedes = super().create(vals_list)
        for sede in sedes:
            sede.receipt_sequence_id = self.env["ir.sequence"].sudo().create({
                "name": f"Justificantes de cobro · {sede.name}",
                "prefix": f"REC-{sede.code.upper()}-%(range_year)s-",
                "padding": 6,
                "use_date_range": True,
                "implementation": "no_gap",  # sin huecos, como el contador de Sistema Propio
                "company_id": sede.company_id.id,
            })
        return sedes

    def _next_receipt_number(self, date):
        self.ensure_one()
        return self.receipt_sequence_id.sudo().next_by_id(sequence_date=date)

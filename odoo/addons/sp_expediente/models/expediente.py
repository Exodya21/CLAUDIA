import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError

AREAS = [("laboral", "Laboral"), ("extranjeria", "Extranjería")]
PREFIJOS = {"laboral": "LAB", "extranjeria": "EXT"}
# Número de expediente dentro de un texto libre (concepto de una transferencia). Tolera los espacios o guiones que
# meten los bancos o el cliente: «LAB 2026 0001», «LAB-2026-0001», «LAB2026/0001» y trozos de la Norma 43.
NUMERO_EN_TEXTO = re.compile(r"\b(LAB|EXT)[\s\-/_.]*(\d{4})[\s\-/_.]*(\d{4})(?!\d)", re.I)


def numeros_en_texto(texto):
    """Números de expediente normalizados (LAB-2026-0001) que aparecen en un texto."""
    return sorted({f"{a.upper()}-{y}-{n}" for a, y, n in NUMERO_EN_TEXTO.findall(texto or "")})


class SpExpediente(models.Model):
    _name = "sp.expediente"
    _description = "Expediente"
    _inherit = ["mail.thread"]
    _order = "fecha_apertura desc, id desc"

    name = fields.Char("Número", readonly=True, copy=False, default=lambda s: _("Nuevo"), index="trigram")
    area = fields.Selection(AREAS, "Área", required=True, tracking=True)
    partner_id = fields.Many2one("res.partner", "Cliente", required=True, tracking=True, index=True)
    company_id = fields.Many2one("res.company", "Compañía", required=True, default=lambda s: s.env.company)
    currency_id = fields.Many2one(related="company_id.currency_id")
    fecha_apertura = fields.Date("Apertura", required=True, default=fields.Date.context_today)
    responsable_id = fields.Many2one("res.users", "Responsable", default=lambda s: s.env.user, tracking=True)
    descripcion = fields.Char("Asunto")
    estado = fields.Selection([("abierto", "Abierto"), ("cerrado", "Cerrado")], default="abierto", required=True,
                              tracking=True)

    _numero_unico = models.UniqueIndex("(company_id, name)")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            area = vals.get("area")
            if not area:
                raise UserError(_("Indique el área del expediente."))
            fecha = vals.get("fecha_apertura") or fields.Date.context_today(self)
            vals["name"] = self.env["ir.sequence"].with_company(vals.get("company_id") or self.env.company.id) \
                .next_by_code(f"sp.expediente.{area}", sequence_date=fecha)
        return super().create(vals_list)

    def write(self, vals):
        if "name" in vals or ("area" in vals and any(e.area != vals["area"] for e in self)):
            raise UserError(_("El número y el área de un expediente no se cambian. Si hay un error, cierre este "
                              "expediente y abra uno nuevo."))
        return super().write(vals)

    def unlink(self):
        raise UserError(_("Los expedientes no se borran: se cierran."))

    @api.model
    def _sp_buscar_en_texto(self, texto, company):
        numeros = numeros_en_texto(texto)
        return numeros, self.search([("name", "in", numeros), ("company_id", "=", company.id)]) if numeros else self.browse()

    def action_cerrar(self):
        self.write({"estado": "cerrado"})

    def action_reabrir(self):
        self.write({"estado": "abierto"})

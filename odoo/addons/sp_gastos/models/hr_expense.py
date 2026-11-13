import logging
from datetime import date

from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.sp_contabilidad.lectura import extraer
from ..lectura import tickets

_logger = logging.getLogger(__name__)

FORMAS = [
    ("propio", "Pagado por la persona (se le reembolsa)"),
    ("efectivo", "Efectivo de la caja de la sede"),
    ("tarjeta", "Tarjeta de empresa"),
]
TIPOS_IVA = (21, 10, 5, 4)


class HrExpense(models.Model):
    _inherit = "hr.expense"

    sp_forma_pago = fields.Selection(FORMAS, "Forma de pago", default="propio", required=True, tracking=True)
    sp_sede_id = fields.Many2one("sp.sede", "Sede", compute="_compute_sp_sede_id", store=True, readonly=False,
                                 help="Sede de la persona. Si el gasto se paga en efectivo, sale de la caja de esta sede.")
    sp_lectura = fields.Json("Datos leídos del ticket", copy=False, readonly=True)
    sp_iva_ticket = fields.Monetary("IVA que figura en el ticket", currency_field="currency_id", copy=False,
                                    help="Lo leído en el ticket. Odoo no lo calcula: si no coincide con el impuesto, "
                                         "se corrige a mano.")

    @api.depends("employee_id")
    def _compute_sp_sede_id(self):
        for e in self:
            if not e.sp_sede_id:
                e.sp_sede_id = e.employee_id.user_id.sp_sede_id

    # --- Forma de pago ---------------------------------------------------------------------------------------
    def _sp_vals_forma(self, forma, sede):
        if forma == "propio":
            return {"payment_mode": "own_account"}
        vals = {"payment_mode": "company_account"}
        if forma == "efectivo":
            if not sede:
                raise UserError(_("Para pagar en efectivo, indique la sede: el gasto sale de su caja."))
            linea = sede.journal_id.outbound_payment_method_line_ids[:1]
            if not linea:
                raise UserError(_("La caja de %s no tiene método de pago de salida.", sede.name))
            vals["payment_method_line_id"] = linea.id
        return vals

    @api.onchange("sp_forma_pago", "sp_sede_id")
    def _onchange_sp_forma_pago(self):
        for e in self:
            if e.sp_forma_pago == "efectivo" and not e.sp_sede_id:
                continue
            e.update(e._sp_vals_forma(e.sp_forma_pago, e.sp_sede_id))

    @api.model_create_multi
    def create(self, vals_list):
        gastos = super().create(vals_list)
        for e, vals in zip(gastos, vals_list):
            if vals.get("sp_forma_pago") and vals["sp_forma_pago"] != "propio":
                e.write(e._sp_vals_forma(e.sp_forma_pago, e.sp_sede_id))
        return gastos

    def write(self, vals):
        res = super().write(vals)
        if "product_id" in vals and not self.env.context.get("sp_forma_interno"):
            self._sp_aplicar_iva_leido()
        if ("sp_forma_pago" in vals or "sp_sede_id" in vals) and not self.env.context.get("sp_forma_interno"):
            for e in self:
                e.with_context(sp_forma_interno=True).write(e._sp_vals_forma(e.sp_forma_pago, e.sp_sede_id))
        return res

    # --- Lectura del ticket ----------------------------------------------------------------------------------
    def _sp_leer(self, datos, mimetype):
        self.ensure_one()
        leido = tickets.parse(extraer.texto(datos, mimetype))
        val = {k: v.get("value") for k, v in leido.items()}
        vals = {"sp_lectura": leido}
        if val.get("expense_date"):
            vals["date"] = date.fromisoformat(val["expense_date"])
        if not self.vendor_id and val.get("supplier_tax_id"):
            nif = val["supplier_tax_id"]
            Partner = self.env["res.partner"]
            proveedor = Partner.search([("vat", "in", [nif, f"ES{nif}"])], limit=1) or Partner.create({
                "name": val.get("supplier_name") or nif, "vat": f"ES{nif}", "country_id": self.env.ref("base.es").id,
                "is_company": nif[0].isalpha() and nif[0] not in "XYZ"})
            vals["vendor_id"] = proveedor.id
        if (not self.name or self.name == self.product_id.display_name) and val.get("supplier_name"):
            vals["name"] = val["supplier_name"]
        if not self.total_amount_currency and val.get("amount_cents"):
            vals["total_amount_currency"] = val["amount_cents"] / 100
        if val.get("vat_cents") is not None:
            vals["sp_iva_ticket"] = val["vat_cents"] / 100
        self.write(vals)
        self._sp_aplicar_iva_leido()
        etiquetas = {"expense_date": _("Fecha"), "supplier_tax_id": _("NIF del comercio"),
                     "supplier_name": _("Comercio"), "amount_cents": _("Total (céntimos)"),
                     "vat_cents": _("IVA (céntimos)")}
        confianza = {"alta": _("alta"), "media": _("media"), "baja": _("baja")}
        filas = "".join(f"<li><b>{escape(etiquetas.get(k, k))}:</b> {escape(str(v.get('value')))} "
                        f"(confianza {confianza.get(v.get('confidence'), '')})</li>" for k, v in leido.items())
        self.message_post(body=Markup("<p>%s</p><ul>%s</ul><p>%s</p>") % (
            _("Lectura del ticket"), Markup(filas) if filas else Markup("<li>—</li>"),
            _("La lectura PROPONE: compruebe los datos con el ticket.")))
        return leido

    def _sp_aplicar_iva_leido(self):
        """Impuesto cuyo tipo reproduce el IVA del ticket (nunca se calcula el IVA). Se vuelve a aplicar si al elegir
        la categoría Odoo cambia los impuestos."""
        for e in self:
            leido = e.sp_lectura or {}
            total = (leido.get("amount_cents") or {}).get("value")
            iva = (leido.get("vat_cents") or {}).get("value")
            if not (total and iva and total > iva):
                continue
            tipo = round(iva * 100 / (total - iva))
            if tipo not in TIPOS_IVA:
                continue
            tax = self.env["account.chart.template"].with_company(e.company_id).ref(
                f"account_tax_template_p_iva{tipo}_bc", raise_if_not_found=False)
            if tax and e.tax_ids != tax:
                e.with_context(sp_forma_interno=True).tax_ids = [(6, 0, tax.ids)]

    def _sp_documento(self):
        self.ensure_one()
        for a in self.message_main_attachment_id | self.attachment_ids:
            if a.mimetype == "application/pdf" or (a.mimetype or "").startswith("image/"):
                return a
        return self.env["ir.attachment"]

    def action_sp_leer_ticket(self):
        for e in self:
            doc = e._sp_documento()
            if not doc:
                raise UserError(_("Adjunte primero la foto o el PDF del ticket."))
            raw = doc.raw
            e._sp_leer(getattr(raw, "content", raw), doc.mimetype)
        return True

    def create_expense_from_attachments(self, attachment_ids=None, view_type="list"):
        ids = super().create_expense_from_attachments(attachment_ids, view_type)
        for e in self.browse(ids if isinstance(ids, list) else []):
            doc = e._sp_documento()
            if doc:
                try:
                    raw = doc.raw
                    e._sp_leer(getattr(raw, "content", raw), doc.mimetype)
                except Exception as ex:  # noqa: BLE001 - subir el ticket no debe fallar por la lectura
                    _logger.warning("No se ha podido leer el ticket %s: %s", doc.name, ex)
        return ids

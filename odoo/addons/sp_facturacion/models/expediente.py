from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.sp_banco.models.account_bank_statement_line import eur

PRODUCTO_HONORARIOS = "Honorarios de expediente"


class SpExpediente(models.Model):
    _inherit = "sp.expediente"

    sp_honorarios = fields.Monetary("Honorarios pactados (base)", currency_field="currency_id", tracking=True,
                                    help="Base imponible, sin IVA ni retención.")
    sp_retencion = fields.Boolean("Cliente con retención de IRPF (15 %)", compute="_compute_sp_retencion", store=True,
                                  readonly=False, tracking=True,
                                  help="Si el cliente es una empresa o un profesional, retiene el 15 % de IRPF. Se propone según el NIF del "
                                       "cliente (Odoo lo considera empresa si tiene NIF de empresa); compruébelo.")
    sale_order_id = fields.Many2one("sale.order", "Pedido de honorarios", readonly=True, copy=False)
    sp_total_pactado = fields.Monetary("Total a pagar por el cliente", compute="_compute_sp_importes",
                                       compute_sudo=True, help="Honorarios + IVA − retención.")
    sp_facturado = fields.Monetary("Facturado", compute="_compute_sp_importes", compute_sudo=True)
    sp_pendiente = fields.Monetary("Pendiente de pago", compute="_compute_sp_importes", compute_sudo=True)
    sp_factura_ids = fields.Many2many("account.move", string="Facturas", compute="_compute_sp_importes",
                                      compute_sudo=True)
    sp_num_facturas = fields.Integer(compute="_compute_sp_importes", compute_sudo=True)
    sp_estado_cobro = fields.Selection([("sin_honorarios", "Sin honorarios"), ("pendiente", "Sin pagos"),
                                        ("en_curso", "Pagando"), ("pagado", "Pagado")], "Cobro",
                                       compute="_compute_sp_importes", compute_sudo=True)

    @api.depends("partner_id.commercial_partner_id.is_company")
    def _compute_sp_retencion(self):
        for e in self:
            e.sp_retencion = bool(e.partner_id.commercial_partner_id.is_company)

    def _sp_facturas_emitidas(self):
        self.ensure_one()
        return self.sale_order_id.invoice_ids.filtered(
            lambda m: m.state == "posted" and m.move_type in ("out_invoice", "out_refund"))

    @api.depends("sale_order_id.amount_total", "sale_order_id.invoice_ids.state", "sale_order_id.invoice_ids.amount_total")
    def _compute_sp_importes(self):
        for e in self:
            facturas = e._sp_facturas_emitidas() if e.sale_order_id else self.env["account.move"]
            e.sp_factura_ids = e.sale_order_id.invoice_ids
            e.sp_num_facturas = len(e.sale_order_id.invoice_ids)
            e.sp_total_pactado = e.sale_order_id.amount_total
            e.sp_facturado = sum(f.amount_total * (-1 if f.move_type == "out_refund" else 1) for f in facturas)
            e.sp_pendiente = e.currency_id.round(e.sp_total_pactado - e.sp_facturado) if e.sale_order_id else 0.0
            if not e.sale_order_id:
                e.sp_estado_cobro = "sin_honorarios"
            elif e.currency_id.is_zero(e.sp_pendiente):
                e.sp_estado_cobro = "pagado"
            else:
                e.sp_estado_cobro = "en_curso" if facturas else "pendiente"

    # ------------------------------------------------------------------------------------------------ honorarios
    def _sp_impuestos(self):
        self.ensure_one()
        co = self.company_id
        ref = lambda x: self.env.ref(f"account.{co.id}_account_tax_template_s_{x}", raise_if_not_found=False)
        iva = ref("iva21s")
        if not iva:
            raise UserError(_("La compañía %s no tiene el IVA 21 %% de servicios del plan español.", co.name))
        irpf = ref("irpf15") if self.sp_retencion else self.env["account.tax"]
        if self.sp_retencion and not irpf:
            raise UserError(_("La compañía %s no tiene la retención de IRPF del 15 %%.", co.name))
        return iva | irpf

    def _sp_producto(self):
        Producto = self.env["product.product"].sudo()
        return Producto.search([("name", "=", PRODUCTO_HONORARIOS), ("company_id", "in", (False, self.company_id.id))],
                               limit=1) or Producto.create({"name": PRODUCTO_HONORARIOS, "type": "service",
                                                            "taxes_id": [Command.clear()]})

    def _sp_tarifa(self):
        """Tarifa en la moneda de la compañía: la del cliente si coincide; si no, una de la compañía (o se crea).
        Evita facturar en otra moneda si la tarifa por defecto se creó antes de cargar el plan contable."""
        self.ensure_one()
        moneda = self.company_id.currency_id
        tarifa = self.partner_id.with_company(self.company_id).property_product_pricelist
        if tarifa.currency_id == moneda:
            return tarifa
        Tarifa = self.env["product.pricelist"].sudo()
        return Tarifa.search([("currency_id", "=", moneda.id), ("company_id", "in", (False, self.company_id.id))],
                             limit=1) or Tarifa.create({"name": _("Honorarios (%s)", moneda.name),
                                                        "currency_id": moneda.id, "company_id": self.company_id.id})

    def _sp_diario(self):
        return self.env["account.journal"].search([("company_id", "=", self.company_id.id), ("type", "=", "sale"),
                                                   ("code", "=", "EXP")], limit=1)

    def action_sp_fijar_honorarios(self):
        """Crea el pedido de honorarios confirmado (lo que después se factura en anticipos y factura final)."""
        for e in self:
            if e.sale_order_id:
                raise UserError(_("Los honorarios de %s ya están fijados. Para cambiarlos, hable con Contabilidad.", e.name))
            if e.sp_honorarios <= 0:
                raise UserError(_("Indique los honorarios pactados (base, sin IVA)."))
            vals = {"partner_id": e.partner_id.id, "company_id": e.company_id.id, "client_order_ref": e.name,
                    "origin": e.name,
                    "order_line": [Command.create({"product_id": e._sp_producto().id, "product_uom_qty": 1,
                                                   "price_unit": e.sp_honorarios,
                                                   "name": _("Honorarios del expediente %(n)s%(a)s", n=e.name,
                                                             a=f" · {e.descripcion}" if e.descripcion else ""),
                                                   "tax_ids": [Command.set(e._sp_impuestos().ids)]})]}
            vals["pricelist_id"] = e._sp_tarifa().id
            diario = e._sp_diario()
            if diario:
                vals["journal_id"] = diario.id
            # El personal de Contabilidad no tiene por qué tener el módulo de Ventas: el pedido es técnico.
            pedido = self.env["sale.order"].sudo().with_company(e.company_id).create(vals)
            pedido.action_confirm()
            e.sale_order_id = pedido
            e.message_post(body=_("Honorarios fijados: %(b)s de base; el cliente pagará %(t)s en total (IVA%(r)s).",
                                  b=eur(e.sp_honorarios), t=eur(pedido.amount_total), r=_(" y retención") if e.sp_retencion else ""))
        return True

    # ------------------------------------------------------------------------------------------------ facturas
    def _sp_fechas(self, fecha_pago):
        """La factura lleva la fecha en que se emite (la serie debe ir en orden de fechas) y la del pago como fecha de
        operación (devengo del anticipo; Verifactu la envía como FechaOperacion si es distinta)."""
        hoy = fields.Date.context_today(self)
        return {"invoice_date": hoy, "delivery_date": fecha_pago if fecha_pago != hoy else False,
                "payment_reference": self.name}

    def _sp_facturar_pago(self, importe, fecha):
        """Emite la factura de un pago de `importe` (IVA y retención incluidos). Si es el primer pago y lo cubre todo,
        factura normal; si no, factura de anticipo. Devuelve la factura emitida."""
        self.ensure_one()
        pedido = self.sale_order_id.sudo()
        if not pedido:
            raise UserError(_("El expediente %s no tiene honorarios fijados.", self.name))
        if importe > self.sp_pendiente + 0.001:
            raise UserError(_("El pago (%(i)s) supera lo pendiente del expediente %(n)s (%(p)s).", i=importe, n=self.name,
                              p=self.sp_pendiente))
        if not self._sp_facturas_emitidas() and self.currency_id.is_zero(importe - pedido.amount_total):
            factura = pedido._create_invoices(final=True)
        else:
            asistente = self.env["sale.advance.payment.inv"].sudo().with_context(
                active_model="sale.order", active_ids=pedido.ids).create(
                {"advance_payment_method": "fixed", "fixed_amount": importe})
            factura = asistente._create_invoices(pedido)
        factura.write(self._sp_fechas(fecha))
        if not self.currency_id.is_zero(factura.amount_total - importe):
            raise UserError(_("La factura preparada (%(f)s) no coincide con el pago (%(i)s). No se emite nada.",
                              f=factura.amount_total, i=importe))
        factura = self.env["account.move"].browse(factura.id)  # se emite como la persona que valida
        factura.action_post()
        return factura

    def _sp_factura_final(self, fecha):
        """Si el expediente ya está pagado y hubo anticipos, emite la factura final (honorarios − anticipos = 0 €)."""
        self.ensure_one()
        pedido = self.sale_order_id.sudo()
        if not pedido or not self.currency_id.is_zero(self.sp_pendiente) or pedido.invoice_status != "to invoice":
            return self.env["account.move"]
        final = pedido._create_invoices(final=True)
        final.write(self._sp_fechas(fecha))
        final = self.env["account.move"].browse(final.id)
        if not self.currency_id.is_zero(final.amount_total):
            self.message_post(body=_("La factura final en borrador %(f)s no sale a 0 € (%(t)s): revísela antes de emitirla.",
                                     f=final.display_name, t=final.amount_total))
            return final
        final.action_post()
        self.message_post(body=_("Expediente pagado: emitida la factura final %s, que descuenta los anticipos.", final.name))
        return final

    def action_sp_ver_facturas(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "res_model": "account.move", "name": _("Facturas de %s", self.name),
                "view_mode": "list,form", "domain": [("id", "in", self.sp_factura_ids.ids)]}

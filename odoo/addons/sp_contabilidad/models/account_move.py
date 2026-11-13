import logging
from datetime import date

from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..lectura import extraer, facturas

_logger = logging.getLogger(__name__)

TIPOS_IVA = (21, 10, 5, 4)
TIPOS_RETENCION = (15, 7, 19, 1, 2)
FACTURAS_RECIBIDAS = ("in_invoice", "in_refund")


class AccountMove(models.Model):
    _inherit = "account.move"

    sp_total_documento = fields.Monetary(
        "Total que figura en la factura", copy=False, tracking=True,
        help="El total impreso en la factura del proveedor. La factura solo se registra si coincide con el total "
             "que calcula Odoo (base + IVA − retención).")
    sp_motivo_duplicado = fields.Text("Motivo (posible factura repetida)", copy=False, tracking=True)
    sp_lectura = fields.Json("Datos leídos", copy=False, readonly=True)
    sp_lectura_confianza = fields.Selection(
        [("alta", "Alta"), ("media", "Media"), ("baja", "Baja")], "Confianza de la lectura", copy=False, readonly=True)

    # --- Lectura ---------------------------------------------------------------------------------------------
    def _sp_cifs_propios(self):
        self.ensure_one()
        propios = {facturas.normalize_tax_id((self.company_id.vat or "").removeprefix("ES"))}
        extra = self.env["ir.config_parameter"].sudo().get_str("sp_contabilidad.cif_propios") or ""
        propios |= {facturas.normalize_tax_id(x) for x in extra.split(",") if x.strip()}
        return {p for p in propios if p}

    def _sp_leer(self, datos, mimetype):
        """Lee el documento y aplica lo leído SOLO en los campos vacíos. Devuelve el diccionario leído."""
        self.ensure_one()
        texto = extraer.texto(datos, mimetype)
        leido = facturas.read_invoice(texto, own_tax_ids=self._sp_cifs_propios(), own_name=self.company_id.name)
        self._sp_aplicar_lectura(leido)
        return leido

    def _sp_proveedor(self, leido):
        cif = leido.get("cif")
        if not cif:
            return self.env["res.partner"]
        Partner = self.env["res.partner"]
        proveedor = Partner.search([("vat", "in", [cif, f"ES{cif}"]), "|", ("company_id", "=", False),
                                    ("company_id", "=", self.company_id.id)], limit=1)
        if not proveedor:
            proveedor = Partner.create({
                "name": leido.get("proveedor_nombre") or cif, "vat": f"ES{cif}", "is_company": cif[0].isalpha()
                and cif[0] not in "XYZ", "country_id": self.env.ref("base.es").id, "supplier_rank": 1})
            self.message_post(body=_("Proveedor dado de alta con los datos leídos: %(n)s (%(c)s). Revíselo.",
                                     n=proveedor.name, c=cif))
        return proveedor

    def _sp_impuesto(self, xmlid):
        return self.env["account.chart.template"].with_company(self.company_id).ref(xmlid, raise_if_not_found=False)

    def _sp_aplicar_lectura(self, leido):
        self.ensure_one()
        vals = {"sp_lectura": leido, "sp_lectura_confianza": leido.get("confianza")}
        if not self.partner_id and (proveedor := self._sp_proveedor(leido)):
            vals["partner_id"] = proveedor.id
        if not self.ref and leido.get("numero"):
            vals["ref"] = leido["numero"]
        if not self.invoice_date and leido.get("fecha"):
            vals["invoice_date"] = date.fromisoformat(leido["fecha"])
        if not self.invoice_date_due and leido.get("vencimiento"):
            vals["invoice_date_due"] = date.fromisoformat(leido["vencimiento"])
        if not self.sp_total_documento and leido.get("total_cents") is not None:
            vals["sp_total_documento"] = leido["total_cents"] / 100
        self.write(vals)
        base = leido.get("base_cents")
        if not self.invoice_line_ids and base:
            impuestos = self.env["account.tax"]
            iva, ret = leido.get("iva_cents"), leido.get("retencion_cents")
            if iva:  # el tipo se RECONOCE a partir de la cifra de la factura; nunca se calcula el IVA
                tipo = round(iva * 100 / base)
                if tipo in TIPOS_IVA:
                    impuestos |= self._sp_impuesto(f"account_tax_template_p_iva{tipo}_sc") or impuestos
            if ret:
                tipo = round(ret * 100 / base)
                if tipo in TIPOS_RETENCION:
                    impuestos |= self._sp_impuesto(f"account_tax_template_p_irpf{tipo}") or impuestos
            self.write({"invoice_line_ids": [(0, 0, {
                "name": _("Factura %s", leido.get("numero") or ""), "quantity": 1, "price_unit": base / 100,
                "tax_ids": [(6, 0, impuestos.ids)]})]})
        self.message_post(body=self._sp_resumen_lectura(leido))

    def _sp_resumen_lectura(self, leido):
        def eur(c):
            return f"{c / 100:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".") if c is not None else "—"
        filas = [
            (_("Número"), leido.get("numero") or "—"), (_("CIF"), leido.get("cif") or "—"),
            (_("Fecha"), leido.get("fecha") or "—"), (_("Vencimiento"), leido.get("vencimiento") or "—"),
            (_("Base"), eur(leido.get("base_cents"))), (_("IVA de la factura"), eur(leido.get("iva_cents"))),
            (_("Retención"), eur(leido.get("retencion_cents"))), (_("Total"), eur(leido.get("total_cents"))),
            (_("¿Cuadra?"), _("Sí") if leido.get("cuadra") else _("No o no se sabe")),
            (_("Confianza"), leido.get("confianza") or "—"),
        ]
        cuerpo = Markup("").join(Markup("<li><b>%s:</b> %s</li>") % (k, v) for k, v in filas)
        aviso = _("La lectura PROPONE: compruebe los datos con la factura antes de registrarla.")
        if leido.get("deducido"):
            aviso += " " + _("Cifras deducidas por aritmética: %s.", ", ".join(map(str, leido["deducido"])))
        return Markup("<p>%s</p><ul>%s</ul><p>%s</p>") % (_("Lectura de la factura"), cuerpo, escape(aviso))

    def _sp_documento(self):
        self.ensure_one()
        adjuntos = self.message_main_attachment_id | self.attachment_ids
        for a in adjuntos:
            if a.mimetype == "application/pdf" or (a.mimetype or "").startswith("image/"):
                return a
        return self.env["ir.attachment"]

    def action_sp_leer_factura(self):
        for move in self:
            if move.move_type not in FACTURAS_RECIBIDAS or move.state != "draft":
                raise UserError(_("Solo se leen facturas de proveedor en borrador."))
            doc = move._sp_documento()
            if not doc:
                raise UserError(_("Adjunte primero el PDF o la foto de la factura."))
            raw = doc.raw  # Odoo 20: BinaryValue (o bytes)
            move._sp_leer(getattr(raw, "content", raw), doc.mimetype)
        return True

    def _extend_with_attachments(self, files_data, new=False):
        res = super()._extend_with_attachments(files_data, new)
        for move in self.filtered(lambda m: m.move_type in FACTURAS_RECIBIDAS and m.state == "draft"
                                  and not m.invoice_line_ids and not m.sp_lectura):
            for fd in files_data:
                mime = fd.get("mimetype") or ""
                if mime == "application/pdf" or mime.startswith("image/"):
                    try:
                        move._sp_leer(fd["raw"], mime)
                    except Exception as e:  # noqa: BLE001 - la subida no debe fallar por la lectura
                        _logger.warning("No se ha podido leer la factura %s: %s", fd.get("name"), e)
                        move.message_post(body=_("No se ha podido leer el documento: rellene los datos a mano."))
                    break
        return res

    # --- Al registrar ----------------------------------------------------------------------------------------
    def _sp_posibles_duplicados(self):
        self.ensure_one()
        base = [("id", "!=", self.id), ("company_id", "=", self.company_id.id), ("move_type", "=", self.move_type),
                ("state", "!=", "cancel"), ("partner_id", "=", self.partner_id.id)]
        parecidas = self.env["account.move"]
        if self.ref:
            parecidas |= self.search(base + [("ref", "=ilike", self.ref.strip())], limit=5)
        if self.invoice_date:
            parecidas |= self.search(base + [("amount_total", "=", self.amount_total),
                                             ("invoice_date", "=", self.invoice_date)], limit=5)
        sumas = self.attachment_ids.mapped("checksum")
        if sumas:
            otros = self.env["ir.attachment"].sudo().search([
                ("checksum", "in", sumas), ("res_model", "=", "account.move"), ("res_id", "!=", self.id)])
            parecidas |= self.search([("id", "in", otros.mapped("res_id")), ("state", "!=", "cancel")])
        return parecidas

    def action_post(self):
        for move in self.filtered(lambda m: m.move_type in FACTURAS_RECIBIDAS and m.state == "draft"):
            if not move.sp_total_documento:
                raise UserError(_("Indique el «Total que figura en la factura» de %s antes de registrarla.",
                                  move.partner_id.display_name or _("la factura")))
            if move.currency_id.compare_amounts(move.amount_total, move.sp_total_documento) != 0:
                raise UserError(_(
                    "La factura no cuadra: Odoo calcula %(odoo)s y la factura dice %(doc)s. El IVA y la retención son "
                    "los que figuran en la factura: ajuste el impuesto o los importes hasta que coincida.",
                    odoo=f"{move.amount_total:.2f}", doc=f"{move.sp_total_documento:.2f}"))
            parecidas = move._sp_posibles_duplicados()
            if parecidas and len((move.sp_motivo_duplicado or "").strip()) < 10:
                lista = "\n".join(f"· {p.name or _('borrador')} · {p.ref or '—'} · "
                                  f"{p.invoice_date or '—'} · {p.amount_total:.2f}" for p in parecidas)
                raise UserError(_(
                    "Esta factura se parece a otra ya registrada:\n%(l)s\n\nSi no es repetida, explique el motivo "
                    "(mínimo 10 caracteres) en «Motivo (posible factura repetida)».", l=lista))
        return super().action_post()

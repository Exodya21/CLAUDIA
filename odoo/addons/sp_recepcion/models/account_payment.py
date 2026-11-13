from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

GRUPO_RESPONSABLE = "sp_recepcion.group_sp_responsable"
TIPOS = [
    ("consulta", "Consulta"),
    ("provision", "Provisión de fondos"),
    ("servicio", "Servicio"),
    ("otro", "Otro"),
]


class AccountPayment(models.Model):
    _inherit = "account.payment"

    # --- Recepción -------------------------------------------------------------------------------------------
    sp_sede_id = fields.Many2one(
        "sp.sede", "Sede", index=True, tracking=True,
        default=lambda s: s.env.user.sp_sede_id if s.env.context.get("sp_recepcion") else False,
        help="Si se indica, es un cobro de recepción: lleva justificante numerado de la sede.")
    sp_tipo = fields.Selection(TIPOS, "Tipo de cobro", tracking=True)
    sp_estado = fields.Selection(
        [("registrado", "Registrado"), ("confirmado", "Confirmado por Contabilidad"), ("anulado", "Anulado")],
        "Estado en recepción", copy=False, tracking=True, readonly=True)
    sp_motivo_duplicado = fields.Text(
        "Motivo (posible cobro repetido)", copy=False, tracking=True,
        help="Obligatorio solo si el sistema avisa de que el cobro se parece a otro ya registrado.")
    sp_justificante_numero = fields.Char("Nº de justificante", copy=False, readonly=True, index=True, tracking=True)
    sp_confirmado_por = fields.Many2one("res.users", "Confirmado por", copy=False, readonly=True)
    sp_confirmado_fecha = fields.Datetime("Confirmado el", copy=False, readonly=True)
    sp_anulado_motivo = fields.Text("Motivo de la anulación", copy=False, readonly=True, tracking=True)
    sp_anulado_por = fields.Many2one("res.users", "Anulado por", copy=False, readonly=True)

    _sp_justificante_uniq = models.Constraint(
        "unique(sp_justificante_numero, company_id)", "El número de justificante ya existe.")

    # --- Duplicados ------------------------------------------------------------------------------------------
    def _sp_posibles_duplicados(self):
        """Cobros parecidos ya registrados: mismo cliente, importe y forma de pago (diario) en ±2 días, o la misma
        referencia en los últimos 90 días. Mismo criterio que Sistema Propio (reception/service.py)."""
        self.ensure_one()
        base = [("id", "!=", self.id), ("company_id", "=", self.company_id.id),
                ("payment_type", "=", "inbound"), ("state", "not in", ("draft", "canceled", "rejected"))]
        dominio = base + [
            ("partner_id", "=", self.partner_id.id), ("amount", "=", self.amount), ("journal_id", "=", self.journal_id.id),
            ("date", ">=", self.date - timedelta(days=2)), ("date", "<=", self.date + timedelta(days=2)),
        ]
        parecidos = self.search(dominio, limit=5)
        ref = (self.memo or "").strip()
        if ref:
            parecidos |= self.search(base + [("memo", "=ilike", ref), ("date", ">=", self.date - timedelta(days=90))],
                                     limit=5)
        return parecidos

    def _sp_avisar_contabilidad(self, resumen, nota):
        grupo = self.env.ref(GRUPO_RESPONSABLE, raise_if_not_found=False)
        usuarios = grupo.sudo().all_user_ids.filtered(lambda u: self.company_id in u.company_ids) if grupo else []
        for usuario in usuarios[:5]:
            self.activity_schedule("mail.mail_activity_data_todo", summary=resumen, note=nota, user_id=usuario.id)

    # --- Registrar (Confirmar de Odoo) -----------------------------------------------------------------------
    def action_post(self):
        recepcion = self.filtered(lambda p: p.sp_sede_id and p.state == "draft")
        for pago in recepcion:
            if pago.payment_type != "inbound" or pago.partner_type != "customer":
                raise UserError(_("Un cobro de recepción debe ser un cobro de cliente."))
            if not pago.partner_id:
                raise UserError(_("Indique de quién se recibe el cobro."))
            if not pago.sp_tipo:
                raise UserError(_("Indique el tipo de cobro (consulta, provisión, servicio u otro)."))
            parecidos = pago._sp_posibles_duplicados()
            if parecidos and len((pago.sp_motivo_duplicado or "").strip()) < 10:
                lista = "\n".join(f"· {p.sp_justificante_numero or p.name} · {p.date:%d/%m/%Y} · "
                                  f"{p.amount:.2f} {p.currency_id.name} · {p.journal_id.name}" for p in parecidos)
                raise UserError(_(
                    "Este cobro se parece a otro ya registrado:\n%(lista)s\n\nSi no es repetido, explique el motivo "
                    "(mínimo 10 caracteres) en «Motivo (posible cobro repetido)» y vuelva a registrarlo. "
                    "Contabilidad lo revisará.", lista=lista))
        res = super().action_post()
        for pago in recepcion:
            vals = {"sp_estado": "registrado"}
            if not pago.sp_justificante_numero:
                vals["sp_justificante_numero"] = pago.sp_sede_id._next_receipt_number(pago.date)
            pago.write(vals)
            pago._sp_generar_justificante()
            if pago.sp_motivo_duplicado:
                pago._sp_avisar_contabilidad(
                    _("Revisar posible cobro repetido"),
                    _("Recepción ha registrado un cobro parecido a otro. Motivo: %s", pago.sp_motivo_duplicado))
        return res

    def _sp_generar_justificante(self):
        """Genera el PDF una sola vez. El informe tiene «attachment_use»: las siguientes impresiones reutilizan
        el adjunto guardado, así que el justificante no cambia aunque cambie la plantilla."""
        informe = self.env.ref("sp_recepcion.action_report_justificante")
        for pago in self:
            informe.sudo()._render_qweb_pdf(informe.report_name, res_ids=pago.ids)

    def action_sp_imprimir_justificante(self):
        self.ensure_one()
        if not self.sp_justificante_numero:
            raise UserError(_("Este cobro aún no tiene justificante: primero hay que registrarlo."))
        return self.env.ref("sp_recepcion.action_report_justificante").report_action(self)

    # --- Confirmar (Contabilidad) ----------------------------------------------------------------------------
    def action_sp_confirmar(self):
        if not self.env.user.has_group(GRUPO_RESPONSABLE):
            raise AccessError(_("Solo Contabilidad (responsable de caja y cobros) puede confirmar cobros."))
        for pago in self:
            if pago.sp_estado != "registrado":
                raise UserError(_("Solo se confirman cobros registrados (%s).", pago.sp_justificante_numero or pago.name))
            pago.write({"sp_estado": "confirmado", "sp_confirmado_por": self.env.uid,
                        "sp_confirmado_fecha": fields.Datetime.now()})
        return True

    # --- Anular (con motivo, desde el asistente) -------------------------------------------------------------
    def _sp_caja_validada(self):
        """¿Hay un cierre de caja validado de la sede de este cobro en su fecha o después?"""
        self.ensure_one()
        cajas = self.env["sp.cierre.caja"].sudo().search([
            ("journal_id", "=", self.journal_id.id), ("estado", "=", "validado"), ("fecha", ">=", self.date)], limit=1)
        return bool(cajas)

    def _sp_anular(self, motivo):
        if not self.env.user.has_group(GRUPO_RESPONSABLE):
            raise AccessError(_("Solo Contabilidad (responsable de caja y cobros) puede anular cobros de recepción."))
        if len((motivo or "").strip()) < 10:
            raise UserError(_("Explique el motivo de la anulación (mínimo 10 caracteres)."))
        for pago in self:
            if pago.sp_estado == "anulado":
                continue
            if pago._sp_caja_validada():
                raise UserError(_("La caja de ese día ya está validada: no se puede anular el cobro %s. Registre una "
                                  "devolución.", pago.sp_justificante_numero))
            super(AccountPayment, pago.with_context(sp_anulacion=True)).action_draft()
            super(AccountPayment, pago.with_context(sp_anulacion=True)).action_cancel()
            pago.write({"sp_estado": "anulado", "sp_anulado_motivo": motivo.strip(), "sp_anulado_por": self.env.uid})
        return True

    def action_draft(self):
        if not self.env.context.get("sp_anulacion") and self.filtered("sp_justificante_numero"):
            raise UserError(_("Un cobro de recepción con justificante no vuelve a borrador: use «Anular cobro», que "
                              "exige motivo."))
        return super().action_draft()

    def action_cancel(self):
        if not self.env.context.get("sp_anulacion") and self.filtered("sp_justificante_numero"):
            raise UserError(_("Un cobro de recepción con justificante solo se anula con «Anular cobro» (con motivo)."))
        return super().action_cancel()

    @api.ondelete(at_uninstall=False)
    def _sp_no_borrar_con_justificante(self):
        if self.filtered("sp_justificante_numero"):
            raise UserError(_("Un cobro con justificante no se borra nunca: se anula con motivo."))

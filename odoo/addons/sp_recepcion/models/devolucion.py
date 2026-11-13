from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

G_RECEPCION = "sp_recepcion.group_sp_recepcion"
G_REVISION = "sp_recepcion.group_sp_devolucion_revision"
G_LETRADO = "sp_recepcion.group_sp_devolucion_letrado"
G_RESPONSABLE = "sp_recepcion.group_sp_responsable"

ESTADOS = [
    ("registrada", "Registrada"),
    ("en_revision", "En revisión"),
    ("escalada_legal", "Escalada al letrado"),
    ("aprobada", "Aprobada · pendiente de pago"),
    ("rechazada", "Rechazada"),
    ("pagada", "Pagada"),
]


class SpDevolucion(models.Model):
    """Devolución de dinero a un cliente (charter 3.9 y 4.4). Referencia: Sistema Propio F5.0 (REFUND_FLOW).

    registrada → en revisión (Atención al cliente investiga) → [escalada al letrado → informe → en revisión]
    → aprobada o rechazada (solo Contabilidad, nunca quien la solicitó) → pagada (Contabilidad registra el pago).
    Una rechazada se puede reabrir con motivo. Nada se borra.
    """
    _name = "sp.devolucion"
    _description = "Devolución a cliente"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"
    _mail_post_access = "read"  # quien la solicitó puede comentar aunque no pueda modificarla

    name = fields.Char("Número", readonly=True, copy=False, default="/")
    company_id = fields.Many2one("res.company", required=True, default=lambda s: s.env.company)
    currency_id = fields.Many2one(related="company_id.currency_id")
    estado = fields.Selection(ESTADOS, default="registrada", required=True, readonly=True, tracking=True)
    partner_id = fields.Many2one("res.partner", "Cliente", required=True, tracking=True)
    importe = fields.Monetary("Importe a devolver", required=True, tracking=True)
    motivo = fields.Text("Motivo de la solicitud", required=True, tracking=True)
    sede_id = fields.Many2one("sp.sede", "Sede", tracking=True, default=lambda s: s.env.user.sp_sede_id)
    cobro_id = fields.Many2one("account.payment", "Cobro original",
                               domain="[('partner_id', '=', partner_id), ('payment_type', '=', 'inbound')]")
    factura_id = fields.Many2one("account.move", "Factura original",
                                 domain="[('partner_id', '=', partner_id), ('move_type', '=', 'out_invoice'), "
                                        "('state', '=', 'posted')]")
    solicitado_por = fields.Many2one("res.users", "Solicitada por", readonly=True, default=lambda s: s.env.user)
    # Revisión (Atención al cliente)
    informe_revision = fields.Text("Informe de la revisión", tracking=True)
    revisado_por = fields.Many2one("res.users", "Revisada por", readonly=True)
    # Letrado
    opinion_legal = fields.Text("Informe del letrado", tracking=True)
    opinion_legal_por = fields.Many2one("res.users", "Informe del letrado por", readonly=True)
    opinion_legal_fecha = fields.Datetime("Informe del letrado el", readonly=True)
    # Decisión y pago (Contabilidad)
    motivo_decision = fields.Text("Motivo de la decisión", tracking=True)
    decidido_por = fields.Many2one("res.users", "Decidida por", readonly=True, tracking=True)
    decidido_fecha = fields.Datetime("Decidida el", readonly=True)
    diario_pago_id = fields.Many2one("account.journal", "Pagar desde",
                                     domain="[('type', 'in', ('cash', 'bank')), ('company_id', '=', company_id)]",
                                     help="Caja de la sede (efectivo) o banco (transferencia, Bizum, TPV).")
    referencia_pago = fields.Char("Referencia del pago", help="Transferencia, Bizum o devolución por TPV/Redsys.")
    pago_id = fields.Many2one("account.payment", "Pago de la devolución", readonly=True)
    rectificativa_id = fields.Many2one("account.move", "Factura rectificativa",
                                       domain="[('partner_id', '=', partner_id), ('move_type', '=', 'out_refund'), "
                                              "('state', '=', 'posted')]",
                                       help="Si la devolución es parcial, haga la rectificativa desde la factura y "
                                            "vincúlela aquí antes de pagar.")
    pagado_por = fields.Many2one("res.users", "Pagada por", readonly=True)
    pagado_fecha = fields.Datetime("Pagada el", readonly=True)

    _importe_positivo = models.Constraint("CHECK (importe > 0)", "El importe a devolver debe ser mayor que cero.")
    _no_decide_quien_solicita = models.Constraint(
        "CHECK (decidido_por IS NULL OR decidido_por <> solicitado_por)",
        "Quien solicita una devolución no puede aprobarla ni rechazarla.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if len((vals.get("motivo") or "").strip()) < 10:
                raise UserError(_("Explique el motivo de la devolución (mínimo 10 caracteres)."))
            vals["name"] = self.env["ir.sequence"].next_by_code("sp.devolucion") or "/"
            vals["solicitado_por"] = self.env.uid
        devoluciones = super().create(vals_list)
        for d in devoluciones:
            d._avisar(G_REVISION, _("Revisar devolución %s", d.name), excluir_xmlid=G_RESPONSABLE)
        return devoluciones

    def write(self, vals):
        protegidos = {"estado", "solicitado_por", "decidido_por", "pagado_por", "pago_id"}
        if protegidos & set(vals) and not self.env.context.get("sp_devolucion_interno"):
            raise UserError(_("El estado de una devolución solo cambia con sus botones."))
        if not self.env.context.get("sp_devolucion_interno"):
            if self.filtered(lambda d: d.estado in ("aprobada", "pagada")) and \
                    {"importe", "partner_id", "factura_id", "cobro_id"} & set(vals):
                raise UserError(_("Una devolución aprobada o pagada no cambia de cliente ni de importe."))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _no_borrar(self):
        raise UserError(_("Las devoluciones no se borran: se rechazan con motivo."))

    # --- Utilidades ------------------------------------------------------------------------------------------
    def _avisar(self, grupo_xmlid, resumen, excluir_xmlid=None):
        """Tarea para las personas del grupo (como mucho 5). Si se indica, se excluyen las de otro grupo (p. ej.
        la revisión va primero a Atención al cliente y, si no hay nadie, a Contabilidad)."""
        grupo = self.env.ref(grupo_xmlid, raise_if_not_found=False)
        if not grupo:
            return
        usuarios = grupo.sudo().all_user_ids.filtered(
            lambda u: self.company_id in u.company_ids and u != self.env.user and u.active and not u.share)
        if excluir_xmlid:
            excluir = self.env.ref(excluir_xmlid).sudo().all_user_ids
            usuarios = (usuarios - excluir) or usuarios
        for u in usuarios[:5]:
            self.sudo().activity_schedule("mail.mail_activity_data_todo", summary=resumen, user_id=u.id)

    def _cerrar_tareas(self, texto):
        """Al dar un paso, las tareas pendientes del paso anterior quedan hechas (constan en el historial)."""
        for d in self:
            d.sudo().activity_ids.action_feedback(feedback=texto)

    def _exigir(self, grupo_xmlid, texto):
        if not self.env.user.has_group(grupo_xmlid):
            raise AccessError(texto)

    def _pasar(self, desde, hacia, **vals):
        for d in self:
            if d.estado not in desde:
                raise UserError(_("La devolución %(n)s está «%(e)s»: no se puede hacer este paso.",
                                  n=d.name, e=dict(ESTADOS)[d.estado]))
        self._cerrar_tareas(_("Paso dado: %s", dict(ESTADOS)[hacia]))
        self.with_context(sp_devolucion_interno=True).write({"estado": hacia, **vals})

    # --- Flujo -----------------------------------------------------------------------------------------------
    def action_revisar(self):
        self._exigir(G_REVISION, _("Solo Atención al cliente o Contabilidad revisan devoluciones."))
        self._pasar(("registrada",), "en_revision", revisado_por=self.env.uid)

    def action_escalar(self):
        self._exigir(G_REVISION, _("Solo Atención al cliente o Contabilidad escalan devoluciones."))
        for d in self:
            if len((d.informe_revision or "").strip()) < 10:
                raise UserError(_("Escriba el informe de la revisión antes de escalarla al letrado."))
        self._pasar(("en_revision",), "escalada_legal")
        for d in self:
            d._avisar(G_LETRADO, _("Informe jurídico para la devolución %s", d.name))

    def action_informe_letrado(self):
        self._exigir(G_LETRADO, _("Solo un letrado emite el informe jurídico de una devolución."))
        for d in self:
            if len((d.opinion_legal or "").strip()) < 10:
                raise UserError(_("Escriba el informe del letrado (mínimo 10 caracteres)."))
        self._pasar(("escalada_legal",), "en_revision", opinion_legal_por=self.env.uid,
                    opinion_legal_fecha=fields.Datetime.now())
        for d in self:
            d._avisar(G_RESPONSABLE, _("Decidir la devolución %s", d.name))

    def _decidir(self, hacia):
        self._exigir(G_RESPONSABLE, _("Solo Contabilidad aprueba o rechaza devoluciones."))
        for d in self:
            if d.solicitado_por == self.env.user:
                raise UserError(_("Quien solicita una devolución no puede aprobarla ni rechazarla."))
            if hacia == "rechazada" and len((d.motivo_decision or "").strip()) < 10:
                raise UserError(_("Explique en «Motivo de la decisión» por qué se rechaza."))
        self._pasar(("registrada", "en_revision"), hacia, decidido_por=self.env.uid,
                    decidido_fecha=fields.Datetime.now())

    def action_aprobar(self):
        self._decidir("aprobada")

    def action_rechazar(self):
        self._decidir("rechazada")

    def action_reabrir(self):
        self._exigir(G_RESPONSABLE, _("Solo Contabilidad reabre devoluciones rechazadas."))
        for d in self:
            if len((d.motivo_decision or "").strip()) < 10:
                raise UserError(_("Explique en «Motivo de la decisión» por qué se reabre."))
            d.message_post(body=_("Reabierta: %s", d.motivo_decision))
        self._pasar(("rechazada",), "en_revision", decidido_por=False, decidido_fecha=False)

    def action_pagar(self):
        """Contabilidad registra el pago. Con factura: rectificativa (total, automática; parcial, vinculada a mano)
        y pago conciliado con ella. Sin factura: pago de salida al cliente. Una devolución por TPV/Redsys se hace
        fuera de Odoo (charter 4.4) y aquí se registra su salida por el banco."""
        self._exigir(G_RESPONSABLE, _("Solo Contabilidad registra el pago de una devolución."))
        for d in self:
            if d.estado != "aprobada":
                raise UserError(_("Solo se pagan devoluciones aprobadas."))
            if not d.diario_pago_id:
                raise UserError(_("Indique desde qué caja o banco se paga."))
            rectificativa = d.rectificativa_id
            if d.factura_id and not d.currency_id.is_zero(d.factura_id.amount_residual) and not rectificativa:
                raise UserError(_("La factura %s no está cobrada del todo: no hay dinero que devolver. Si hay que "
                                  "anularla, haga una factura rectificativa sin devolución.", d.factura_id.name))
            if d.factura_id and not rectificativa:
                if d.currency_id.compare_amounts(d.importe, d.factura_id.amount_total) != 0:
                    raise UserError(_("La devolución es parcial: haga la factura rectificativa desde la factura %s "
                                      "por el importe a devolver y vincúlela antes de pagar.", d.factura_id.name))
                rectificativa = d.factura_id._reverse_moves(
                    [{"ref": _("Devolución %s", d.name), "invoice_date": fields.Date.context_today(d)}])
                rectificativa.action_post()
            if rectificativa:
                pago = self.env["account.payment.register"].with_context(
                    active_model="account.move", active_ids=rectificativa.ids).create({
                        "amount": d.importe, "journal_id": d.diario_pago_id.id,
                        "communication": d.referencia_pago or d.name})._create_payments()
            else:
                pago = self.env["account.payment"].create({
                    "payment_type": "outbound", "partner_type": "customer", "partner_id": d.partner_id.id,
                    "amount": d.importe, "journal_id": d.diario_pago_id.id,
                    "memo": d.referencia_pago or d.name})
                pago.action_post()
            d._pasar(("aprobada",), "pagada", pago_id=pago.id, rectificativa_id=rectificativa.id or False,
                     pagado_por=self.env.uid, pagado_fecha=fields.Datetime.now())
        return True

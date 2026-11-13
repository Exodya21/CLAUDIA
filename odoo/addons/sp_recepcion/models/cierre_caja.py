from datetime import datetime, time

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

GRUPO_RESPONSABLE = "sp_recepcion.group_sp_responsable"


class SpCierreCaja(models.Model):
    """Cierre de caja diario de una sede: una persona cuenta el efectivo y otra DISTINTA lo valida.
    Referencia: Sistema Propio F5.2 (close_day / validación del cierre)."""
    _name = "sp.cierre.caja"
    _description = "Cierre de caja diario"
    _inherit = ["mail.thread"]
    _order = "fecha desc, sede_id"

    name = fields.Char(compute="_compute_name", store=True)
    sede_id = fields.Many2one("sp.sede", "Sede", required=True, tracking=True,
                              default=lambda s: s.env.user.sp_sede_id)
    company_id = fields.Many2one(related="sede_id.company_id", store=True)
    journal_id = fields.Many2one(related="sede_id.journal_id", store=True, string="Caja")
    currency_id = fields.Many2one(related="company_id.currency_id")
    fecha = fields.Date("Día", required=True, default=fields.Date.context_today, tracking=True)
    estado = fields.Selection(
        [("borrador", "Borrador"), ("pendiente", "Contado · pendiente de validar"), ("validado", "Validado"),
         ("rechazado", "Rechazado")], default="borrador", required=True, tracking=True, readonly=True)
    esperado = fields.Monetary("Saldo según registros", readonly=True, tracking=True,
                               help="Saldo de la cuenta de la caja al final del día, según los movimientos registrados.")
    contado = fields.Monetary("Efectivo contado", tracking=True)
    diferencia = fields.Monetary("Diferencia (contado − registros)", readonly=True, tracking=True)
    notas = fields.Text("Notas del recuento", help="Obligatorias si hay diferencia.")
    contado_por = fields.Many2one("res.users", "Contado por", readonly=True, tracking=True)
    contado_fecha = fields.Datetime("Contado el", readonly=True)
    validado_por = fields.Many2one("res.users", "Validado / rechazado por", readonly=True, tracking=True)
    validado_fecha = fields.Datetime("Validado / rechazado el", readonly=True)
    nota_validacion = fields.Text("Nota de la validación o del rechazo", tracking=True)
    ajuste_move_id = fields.Many2one("account.move", "Asiento de ajuste", readonly=True)

    # Refuerzo en la BASE DE DATOS (como los triggers de Sistema Propio): aunque alguien salte el código de Odoo,
    # quien valida o rechaza nunca es quien contó, y un cierre validado o rechazado no cambia ni se borra.
    _sp_otra_persona = models.Constraint(
        "CHECK (validado_por IS NULL OR contado_por IS NULL OR validado_por <> contado_por)",
        "El cierre lo tiene que validar o rechazar una persona distinta de la que ha contado la caja.")

    def init(self):
        self.env.cr.execute("""
            CREATE OR REPLACE FUNCTION sp_cierre_caja_proteger() RETURNS trigger AS $$
            BEGIN
                IF TG_OP = 'DELETE' THEN
                    IF OLD.estado IN ('pendiente', 'validado') THEN
                        RAISE EXCEPTION 'Un cierre de caja contado o validado no se borra (sp_cierre_caja %)', OLD.id;
                    END IF;
                    RETURN OLD;
                END IF;
                IF OLD.estado IN ('validado', 'rechazado') AND (
                       NEW.estado IS DISTINCT FROM OLD.estado OR NEW.sede_id IS DISTINCT FROM OLD.sede_id
                    OR NEW.fecha IS DISTINCT FROM OLD.fecha OR NEW.esperado IS DISTINCT FROM OLD.esperado
                    OR NEW.contado IS DISTINCT FROM OLD.contado OR NEW.diferencia IS DISTINCT FROM OLD.diferencia
                    OR NEW.contado_por IS DISTINCT FROM OLD.contado_por
                    OR NEW.validado_por IS DISTINCT FROM OLD.validado_por
                    OR NEW.ajuste_move_id IS DISTINCT FROM OLD.ajuste_move_id) THEN
                    RAISE EXCEPTION 'Un cierre de caja validado o rechazado no se modifica (sp_cierre_caja %)', OLD.id;
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            DROP TRIGGER IF EXISTS sp_cierre_caja_proteger ON sp_cierre_caja;
            CREATE TRIGGER sp_cierre_caja_proteger BEFORE UPDATE OR DELETE ON sp_cierre_caja
                FOR EACH ROW EXECUTE FUNCTION sp_cierre_caja_proteger();
        """)

    @api.depends("sede_id", "fecha")
    def _compute_name(self):
        for c in self:
            c.name = f"Caja {c.sede_id.name or ''} · {c.fecha:%d/%m/%Y}" if c.fecha else "Cierre de caja"

    # --- Reglas ----------------------------------------------------------------------------------------------
    @api.constrains("sede_id", "fecha", "estado")
    def _check_uno_por_dia(self):
        for c in self:
            if c.estado == "rechazado":
                continue
            otros = self.search_count([("id", "!=", c.id), ("sede_id", "=", c.sede_id.id), ("fecha", "=", c.fecha),
                                       ("estado", "!=", "rechazado")])
            if otros:
                raise ValidationError(_("Ya hay un cierre de la caja de %(sede)s del %(dia)s. Si hay que rehacerlo, el "
                                        "responsable debe rechazar el anterior.", sede=c.sede_id.name,
                                        dia=c.fecha.strftime("%d/%m/%Y")))

    def write(self, vals):
        if not self.env.context.get("sp_cierre_interno"):
            bloqueados = self.filtered(lambda c: c.estado in ("validado", "rechazado"))
            if bloqueados and set(vals) - {"message_main_attachment_id"}:
                raise UserError(_("Un cierre validado o rechazado no se modifica."))
            if self.filtered(lambda c: c.estado == "pendiente") and set(vals) & {"contado", "notas", "sede_id", "fecha"}:
                raise UserError(_("El recuento ya está hecho. Si es incorrecto, el responsable debe rechazarlo."))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _no_borrar(self):
        if self.filtered(lambda c: c.estado in ("pendiente", "validado")):
            raise UserError(_("Un cierre contado o validado no se borra."))

    # --- Cálculo ---------------------------------------------------------------------------------------------
    def _saldo_registros(self):
        """Suma de los apuntes publicados en la cuenta de la caja hasta el final del día (determinista)."""
        self.ensure_one()
        cuenta = self.journal_id.default_account_id
        if not cuenta:
            raise UserError(_("La caja de la sede no tiene cuenta contable."))
        grupos = self.env["account.move.line"].sudo()._read_group(
            [("account_id", "=", cuenta.id), ("parent_state", "=", "posted"), ("date", "<=", self.fecha),
             ("company_id", "=", self.company_id.id)], [], ["balance:sum"])
        return self.currency_id.round(grupos[0][0] or 0.0)

    # --- Acciones --------------------------------------------------------------------------------------------
    def action_contar(self):
        for c in self:
            if c.estado != "borrador":
                raise UserError(_("Este cierre ya se ha contado."))
            esperado = c._saldo_registros()
            diferencia = c.currency_id.round(c.contado - esperado)
            if not c.currency_id.is_zero(diferencia) and len((c.notas or "").strip()) < 5:
                raise UserError(_("Hay %(dif)s de diferencia entre lo contado y lo registrado: explique el motivo en "
                                  "«Notas del recuento».", dif=f"{diferencia:.2f} {c.currency_id.symbol}"))
            c.with_context(sp_cierre_interno=True).write({
                "esperado": esperado, "diferencia": diferencia, "estado": "pendiente",
                "contado_por": self.env.uid, "contado_fecha": fields.Datetime.now()})
        return True

    def _comprobar_responsable(self):
        if not self.env.user.has_group(GRUPO_RESPONSABLE):
            raise AccessError(_("Solo un responsable de caja (Contabilidad) puede validar o rechazar cierres."))
        for c in self:
            if c.estado != "pendiente":
                raise UserError(_("Solo se validan o rechazan cierres contados y pendientes."))
            if c.contado_por == self.env.user:
                raise UserError(_("El cierre lo tiene que validar una persona distinta de la que ha contado la caja."))

    def action_validar(self):
        self._comprobar_responsable()
        for c in self:
            if not c.currency_id.is_zero(c._saldo_registros() - c.esperado):
                raise UserError(_("Ha habido movimientos en la caja desde el recuento. Rechace este cierre y vuelva a "
                                  "contar."))
            vals = {"estado": "validado", "validado_por": self.env.uid, "validado_fecha": fields.Datetime.now()}
            if not c.currency_id.is_zero(c.diferencia):
                vals["ajuste_move_id"] = c._crear_ajuste().id
            c.with_context(sp_cierre_interno=True).write(vals)
        return True

    def action_rechazar(self):
        self._comprobar_responsable()
        for c in self:
            if len((c.nota_validacion or "").strip()) < 5:
                raise UserError(_("Explique en «Nota de la validación o del rechazo» por qué se rechaza el cierre."))
            c.with_context(sp_cierre_interno=True).write(
                {"estado": "rechazado", "validado_por": self.env.uid, "validado_fecha": fields.Datetime.now()})
        return True

    def _crear_ajuste(self):
        """Asiento del descuadre: sobrante a ingresos, faltante a gastos (cuentas de diferencias de la caja)."""
        self.ensure_one()
        j = self.journal_id
        cuenta_caja = j.default_account_id
        if self.diferencia > 0:
            contrapartida = j.profit_account_id or self.company_id.default_cash_difference_income_account_id
        else:
            contrapartida = j.loss_account_id or self.company_id.default_cash_difference_expense_account_id
        if not contrapartida:
            raise UserError(_("Configure en la caja las cuentas de diferencias (beneficio y pérdida)."))
        importe = abs(self.diferencia)
        signo = 1 if self.diferencia > 0 else -1
        move = self.env["account.move"].sudo().create({
            "move_type": "entry", "journal_id": j.id, "date": self.fecha, "company_id": self.company_id.id,
            "ref": _("Ajuste de arqueo · %s · %s", self.name, (self.notas or "").strip()[:120]),
            "line_ids": [
                (0, 0, {"account_id": cuenta_caja.id, "name": _("Ajuste de arqueo"),
                        "debit": importe if signo > 0 else 0.0, "credit": importe if signo < 0 else 0.0}),
                (0, 0, {"account_id": contrapartida.id, "name": _("Ajuste de arqueo"),
                        "debit": importe if signo < 0 else 0.0, "credit": importe if signo > 0 else 0.0}),
            ],
        })
        move.action_post()
        return move

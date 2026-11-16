import json
import logging
import secrets
from datetime import date, datetime, timedelta

from odoo import Command, _, api, fields, models
from odoo.exceptions import AccessError, UserError

from odoo.addons.base.models.res_partner_bank import sanitize_account_number
from odoo.addons.sp_banco.lectura.extractos import Statement
from odoo.addons.sp_cifrado import cifrado
from odoo.addons.sp_cifrado.models.campo import CharCifrado

from ..proveedores import enablebanking as eb

_logger = logging.getLogger(__name__)
G_CONTA = "sp_recepcion.group_sp_responsable"
RUTA_VUELTA = "/sp_banco_psd2/vuelta"
DIAS_PRIMERA_CARGA = 90
SOLAPE = 3  # días que se vuelven a pedir en cada vuelta por si el banco contabiliza con retraso
DIAS_AVISO = 15


class SpBancoConexion(models.Model):
    _name = "sp.banco.conexion"
    _description = "Conexión directa con un banco (PSD2)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char("Banco", required=True, help="Nombre del banco tal como lo da el agregador (p. ej. «CaixaBank»).")
    pais = fields.Char("País", default="ES", required=True, size=2)
    tipo = fields.Selection([("business", "Empresa"), ("personal", "Particular")], "Tipo de banca", default="business",
                            required=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda s: s.env.company)
    proveedor = fields.Selection([("enablebanking", "Enable Banking")], default="enablebanking", required=True,
                                 readonly=True)
    estado = fields.Selection([("borrador", "Sin autorizar"), ("pendiente", "Esperando la autorización del banco"),
                               ("activa", "Activa"), ("caducada", "Caducada: hay que renovar"),
                               ("revocada", "Revocada"), ("error", "Error")], default="borrador", required=True,
                              tracking=True, readonly=True)
    estado_token = fields.Char(copy=False, readonly=True, groups="base.group_system")
    sesion_id = CharCifrado("Sesión", copy=False, readonly=True, groups="base.group_system")
    valido_hasta = fields.Datetime("Consentimiento válido hasta", readonly=True, tracking=True)
    aviso_enviado = fields.Boolean(copy=False, readonly=True)
    ultima_sync = fields.Datetime("Última sincronización", readonly=True)
    ultimo_error = fields.Text("Último aviso", readonly=True)
    cuenta_ids = fields.One2many("sp.banco.conexion.cuenta", "conexion_id", "Cuentas")
    url_vuelta = fields.Char("Dirección de vuelta", compute="_compute_url_vuelta",
                             help="Hay que registrarla en la aplicación del agregador (con https en producción).")

    def _compute_url_vuelta(self):
        base = self.env["ir.config_parameter"].sudo().get_str("web.base.url") or ""
        for c in self:
            c.url_vuelta = base.rstrip("/") + RUTA_VUELTA

    def _sp_exigir(self):
        if not self.env.user.has_group(G_CONTA):
            raise AccessError(_("Solo Contabilidad gestiona las conexiones con los bancos."))

    # ------------------------------------------------------------------------------------------------ autorizar
    def action_autorizar(self):
        """Abre la banca del despacho para dar (o renovar) el consentimiento."""
        self.ensure_one()
        self._sp_exigir()
        estado = secrets.token_urlsafe(24)
        valido = fields.Datetime.now() + timedelta(days=eb.MAX_DIAS_CONSENTIMIENTO)
        try:
            url = eb.iniciar_autorizacion(self.name, self.pais, valido, self.url_vuelta, estado, self.tipo)
        except eb.ErrorProveedor as e:
            raise UserError(e.mensaje) from e
        self.sudo().write({"estado_token": estado, "estado": "pendiente", "ultimo_error": False})
        self.message_post(body=_("%s ha pedido la autorización al banco.", self.env.user.name))
        return {"type": "ir.actions.act_url", "url": url, "target": "self"}

    @api.model
    def _sp_vuelta(self, estado, codigo=None, error=None):
        """Vuelta desde el banco (controlador). Devuelve la conexión."""
        self._sp_exigir()
        conexion = self.sudo().search([("estado_token", "=", estado), ("estado", "=", "pendiente")], limit=1) \
            if estado else self.browse()
        if not conexion:
            raise UserError(_("Esta autorización no corresponde a ninguna conexión pendiente (o ya se usó)."))
        conexion.estado_token = False  # un solo uso
        if error or not codigo:
            conexion.write({"estado": "error", "ultimo_error": _("El banco no ha dado la autorización (%s).", error or "-")})
            return conexion
        try:
            sesion = eb.crear_sesion(codigo)
        except eb.ErrorProveedor as e:
            conexion.write({"estado": "error", "ultimo_error": e.mensaje})
            return conexion
        conexion._sp_guardar_sesion(sesion)
        return conexion

    def _sp_guardar_sesion(self, sesion):
        self.ensure_one()
        hasta = (sesion.get("access") or {}).get("valid_until")
        valido = fields.Datetime.to_datetime(hasta[:19].replace("T", " ")) if hasta else \
            fields.Datetime.now() + timedelta(days=eb.MAX_DIAS_CONSENTIMIENTO)
        diarios = self.env["account.journal"].sudo().search([("type", "=", "bank"), ("company_id", "=", self.company_id.id)])
        por_iban = {sanitize_account_number(j.bank_account_id.account_number): j for j in diarios if j.bank_account_id}
        cuentas = [Command.clear()]
        for a in sesion.get("accounts") or []:
            iban = ((a.get("account_id") or {}).get("iban")) or ""
            diario = por_iban.get(sanitize_account_number(iban))
            cuentas.append(Command.create({"uid": a.get("uid"), "iban": iban or False,
                                           "nombre": a.get("name") or a.get("product") or False,
                                           "journal_id": diario.id if diario else False}))
        self.write({"sesion_id": sesion.get("session_id"), "valido_hasta": valido, "estado": "activa",
                    "aviso_enviado": False, "ultimo_error": False, "cuenta_ids": cuentas})
        sin = self.cuenta_ids.filtered(lambda c: not c.journal_id)
        self.message_post(body=_("Autorización concedida hasta el %(f)s: %(n)s cuentas%(s)s.", f=valido.strftime("%d/%m/%Y"),
                                 n=len(self.cuenta_ids),
                                 s=_("; %s sin diario: elíjalo a mano", len(sin)) if sin else ""))

    def action_revocar(self):
        self._sp_exigir()
        for c in self:
            sesion = c.sudo().sesion_id
            if sesion and not sesion.startswith("["):
                try:
                    eb.borrar_sesion(sesion)
                except eb.ErrorProveedor as e:
                    c.message_post(body=_("El agregador no ha confirmado la revocación: %s", e.mensaje))
            c.sudo().write({"estado": "revocada", "sesion_id": False, "estado_token": False})
            c.message_post(body=_("Conexión revocada por %s.", self.env.user.name))
        return True

    # ------------------------------------------------------------------------------------------------ sincronizar
    def action_sincronizar(self):
        self._sp_exigir()
        res = self._sp_sincronizar()
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"title": _("Sincronización"), "message": res, "sticky": False,
                           "next": {"type": "ir.actions.act_window_close"}}}

    def _sp_sincronizar(self, hoy=None):
        hoy = hoy or date.today()
        resumen = []
        for c in self.sudo().filtered(lambda c: c.estado == "activa"):
            if c.valido_hasta and c.valido_hasta <= fields.Datetime.now():
                c.write({"estado": "caducada", "ultimo_error": _("El consentimiento ha caducado: pulse «Autorizar».")})
                c._sp_avisar(_("La conexión con %s ha caducado. Hay que volver a autorizarla en el banco.", c.name))
                continue
            for cuenta in c.cuenta_ids.filtered(lambda x: x.journal_id and x.activa):
                desde = (cuenta.ultima_fecha or hoy - timedelta(days=DIAS_PRIMERA_CARGA)) - timedelta(days=SOLAPE)
                try:
                    trans = eb.movimientos(cuenta.uid, desde, hoy)
                except eb.ErrorProveedor as e:
                    c.ultimo_error = e.mensaje
                    resumen.append(f"{c.name}: {e.mensaje}")
                    if not e.limite and e.estado in (401, 403, 410):
                        c.write({"estado": "caducada"})
                        c._sp_avisar(_("El banco %s ya no acepta la autorización: hay que renovarla.", c.name))
                    break
                n = cuenta._sp_registrar(trans, desde, hoy)
                resumen.append(_("%(c)s: %(n)s movimientos nuevos", c=cuenta.journal_id.name, n=n))
            else:
                c.write({"ultima_sync": fields.Datetime.now(), "ultimo_error": False})
        return "; ".join(resumen) or _("No hay conexiones activas con cuentas asignadas.")

    def _sp_avisar(self, texto):
        """Actividad para Contabilidad en la conexión."""
        grupo = self.env.ref(G_CONTA)
        usuarios = grupo.all_user_ids if "all_user_ids" in grupo._fields else grupo.user_ids
        for u in usuarios.filtered(lambda u: self.company_id in u.company_ids and not u.share)[:3]:
            self.activity_schedule("mail.mail_activity_data_todo", user_id=u.id, summary=_("Conexión con el banco"),
                                   note=texto)

    @api.model
    def _sp_cron(self):
        conexiones = self.sudo().search([("estado", "=", "activa")])  # tarea programada del sistema
        limite = fields.Datetime.now() + timedelta(days=DIAS_AVISO)
        for c in conexiones.filtered(lambda c: c.valido_hasta and c.valido_hasta <= limite and not c.aviso_enviado):
            c._sp_avisar(_("La autorización con %(b)s caduca el %(f)s: renuévela con «Autorizar en el banco».",
                           b=c.name, f=c.valido_hasta.strftime("%d/%m/%Y")))
            c.aviso_enviado = True
        conexiones._sp_sincronizar()


class SpBancoConexionCuenta(models.Model):
    _name = "sp.banco.conexion.cuenta"
    _description = "Cuenta de una conexión PSD2"

    conexion_id = fields.Many2one("sp.banco.conexion", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="conexion_id.company_id", store=True)
    uid = CharCifrado("Identificador en el agregador", readonly=True, groups="base.group_system")
    iban = CharCifrado("IBAN", readonly=True)
    iban_visible = fields.Char("Cuenta", compute="_compute_iban_visible")
    nombre = fields.Char("Nombre en el banco", readonly=True)
    journal_id = fields.Many2one("account.journal", "Diario", domain="[('type', '=', 'bank'), ('company_id', '=', company_id)]",
                                 help="Diario de banco al que van los movimientos. Se asigna solo si el IBAN coincide.")
    activa = fields.Boolean("Sincronizar", default=True)
    ultima_fecha = fields.Date("Movimientos hasta", readonly=True)

    @api.depends("iban")
    def _compute_iban_visible(self):
        for c in self:
            c.iban_visible = cifrado.enmascarar(c.iban)

    @api.constrains("journal_id", "iban")
    def _check_diario(self):
        for c in self.filtered("journal_id"):
            propio = sanitize_account_number(c.journal_id.bank_account_id.account_number or "")
            if propio and c.iban and propio != sanitize_account_number(c.iban):
                raise UserError(_("El diario %(d)s es de otra cuenta (%(a)s), no de %(b)s.", d=c.journal_id.name,
                                  a=cifrado.enmascarar(propio), b=c.iban_visible))

    def _sp_registrar(self, transacciones, desde, hasta):
        """Pasa los movimientos al importador de sp_banco. Devuelve cuántos son nuevos."""
        self.ensure_one()
        lineas = eb.a_lineas(transacciones, sanitize_account_number(self.iban or ""))
        if not lineas:
            return 0
        Line = self.env["account.bank.statement.line"].sudo()
        existentes = set(Line.search([("journal_id", "=", self.journal_id.id),
                                      ("sp_ext_id", "in", [ln.ext_id for ln in lineas])]).mapped("sp_ext_id"))
        nuevas = [ln for ln in lineas if ln.ext_id not in existentes]
        ultima = max(ln.booking_date for ln in lineas)
        if nuevas:
            st = Statement(file_format="PSD2 · Enable Banking", account_hint=None, period_from=desde, period_to=hasta,
                           lines=lineas)
            original = json.dumps({"proveedor": "enablebanking", "desde": str(desde), "hasta": str(hasta),
                                   "transactions": transacciones}, ensure_ascii=False).encode()
            nombre = f"PSD2 {self.journal_id.code} {desde:%d/%m/%Y}–{hasta:%d/%m/%Y}"
            self.env["sp.banco.importacion"].sudo().with_company(self.company_id)._sp_registrar(
                nombre, original, st, self.journal_id)
        self.ultima_fecha = max(ultima, self.ultima_fecha or ultima)
        return len(nuevas)

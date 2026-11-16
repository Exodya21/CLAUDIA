import hashlib
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.sp_cifrado import cifrado

from ..lectura import extractos

_logger = logging.getLogger(__name__)


class SpBancoImportacion(models.Model):
    """Registro de cada extracto importado (o solo comprobado). El original queda adjunto y no se modifica."""
    _name = "sp.banco.importacion"
    _description = "Importación de extracto bancario"
    _inherit = ["mail.thread"]
    _order = "id desc"

    name = fields.Char("Archivo", required=True, readonly=True)
    company_id = fields.Many2one("res.company", required=True, readonly=True, default=lambda s: s.env.company)
    currency_id = fields.Many2one(related="company_id.currency_id")
    journal_id = fields.Many2one("account.journal", "Cuenta (diario de banco)", readonly=True)
    formato = fields.Char(readonly=True)
    solo_comprobar = fields.Boolean("Solo comprobado (no importado)", readonly=True)
    desde = fields.Date(readonly=True)
    hasta = fields.Date(readonly=True)
    saldo_inicial = fields.Monetary(readonly=True)
    saldo_final = fields.Monetary(readonly=True)
    cuadra = fields.Selection([("si", "Sí"), ("no", "No"), ("nd", "El archivo no trae saldos")],
                              "¿Cuadran los saldos?", readonly=True,
                              help="Saldo inicial + movimientos = saldo final, según el propio archivo.")
    total = fields.Integer("Movimientos en el archivo", readonly=True)
    nuevos = fields.Integer("Movimientos nuevos", readonly=True)
    duplicados = fields.Integer("Ya importados (no se duplican)", readonly=True)
    errores = fields.Text("Líneas con error (no importadas)", readonly=True)
    columnas = fields.Text("Columnas reconocidas", readonly=True)
    statement_id = fields.Many2one("account.bank.statement", "Extracto", readonly=True)
    huella = fields.Char("Huella del archivo (SHA-256)", readonly=True)
    original_id = fields.Many2one("ir.attachment", "Original (cifrado)", readonly=True,
                                  help="El extracto original se guarda cifrado: solo Contabilidad lo descarga en claro.")

    @api.model
    def _sp_diario_por_cuenta(self, hint, diario_elegido):
        """Cuenta por los últimos dígitos del IBAN que trae el archivo. Si no los trae o hay dos que coinciden, NO se
        adivina: se usa la cuenta elegida o se pide elegirla."""
        bancos = self.env["account.journal"].search([("type", "=", "bank"), ("company_id", "in", self.env.companies.ids)])
        if hint:
            coinciden = bancos.filtered(lambda j: (j.bank_account_id.sanitized_account_number or j.bank_account_id.account_number or "").replace(" ", "").endswith(hint))
            if len(coinciden) == 1:
                if diario_elegido and diario_elegido != coinciden:
                    raise UserError(_("El archivo es de la cuenta terminada en %(h)s (%(c)s), no de %(e)s.",
                                      h=hint, c=coinciden.name, e=diario_elegido.name))
                return coinciden
            if len(coinciden) > 1:
                if diario_elegido in coinciden:
                    return diario_elegido
                raise UserError(_("Hay varias cuentas terminadas en %s: elija la cuenta.", hint))
        if diario_elegido:
            return diario_elegido
        raise UserError(_("El archivo no indica la cuenta (o no coincide con ninguna): elija la cuenta."))

    @api.model
    def _sp_importar(self, nombre, datos, diario_elegido=False, solo_comprobar=False):
        try:
            st = extractos.parse(datos, nombre)
        except extractos.ParseError as e:
            raise UserError(_("%(f)s: %(m)s", f=nombre, m=e.message)) from e
        diario = self._sp_diario_por_cuenta(st.account_hint, diario_elegido)
        Line = self.env["account.bank.statement.line"]
        existentes = set(Line.search([("journal_id", "=", diario.id), ("sp_ext_id", "in", [ln.ext_id for ln in st.lines])])
                         .mapped("sp_ext_id"))
        nuevas = [ln for ln in st.lines if ln.ext_id not in existentes]
        if st.opening_cents is not None and st.closing_cents is not None:
            cuadra = "si" if st.opening_cents + sum(ln.amount_cents for ln in st.lines) == st.closing_cents else "no"
        else:
            cuadra = "nd"
        vals = {
            "name": nombre, "company_id": diario.company_id.id, "journal_id": diario.id, "formato": st.file_format,
            "solo_comprobar": solo_comprobar, "desde": st.period_from, "hasta": st.period_to,
            "saldo_inicial": (st.opening_cents or 0) / 100, "saldo_final": (st.closing_cents or 0) / 100,
            "cuadra": cuadra, "total": len(st.lines), "nuevos": len(nuevas), "duplicados": len(st.lines) - len(nuevas),
            "errores": "\n".join(f"Línea {e.get('linea', '?')}: {e.get('error', e)}"
                                 for e in st.errors) or False,
            "columnas": ", ".join(f"{k} → {v}" for k, v in (st.columns or {}).items()) or False,
            "huella": hashlib.sha256(datos).hexdigest(),
        }
        imp = self.create(vals)
        if solo_comprobar:
            return imp
        # El original se guarda tal cual y nadie lo puede cambiar (la importación no se modifica): adjunto técnico.
        # Se guarda CIFRADO (sp_cifrado, clave fuera de la base de datos): una copia del almacén de archivos no lo revela.
        try:
            cifrado_ = cifrado.cifrar_archivo(datos)
        except cifrado.SinClave as e:
            raise UserError(str(e)) from e
        imp.sudo().original_id = self.env["ir.attachment"].sudo().create({
            "name": f"{nombre}.cifrado", "raw": cifrado_, "mimetype": "application/octet-stream",
            "res_model": self._name, "res_id": imp.id})
        if nuevas:
            extracto = self.env["account.bank.statement"].create({
                "name": f"{diario.code} {st.period_from:%d/%m/%Y}–{st.period_to:%d/%m/%Y}",
                "journal_id": diario.id, "reference": nombre,
                "balance_start": (st.opening_cents or 0) / 100 if st.opening_cents is not None else 0.0,
                "balance_end_real": (st.closing_cents / 100) if st.closing_cents is not None else False,
            })
            Line.create([{
                "journal_id": diario.id, "statement_id": extracto.id, "date": ln.booking_date,
                "payment_ref": ln.description or ln.reference or "/", "amount": ln.amount_cents / 100,
                "partner_name": ln.counterparty or False, "sp_ext_id": ln.ext_id, "sp_referencia": ln.reference,
                "sp_fecha_valor": ln.value_date, "sp_importacion_id": imp.id,
            } for ln in nuevas])
            imp.sudo().statement_id = extracto  # la importación no la modifica nadie; el enlace lo pone el sistema
            # Propuestas de conciliación: el sistema propone; Contabilidad valida.
            extracto.line_ids._sp_proponer()
        return imp

    def action_sp_descargar_original(self):
        self.ensure_one()
        if not self.env.user.has_group("sp_recepcion.group_sp_responsable"):
            raise UserError(_("Solo Contabilidad descarga los extractos originales."))
        if not self.original_id:
            raise UserError(_("Esta importación no tiene el original guardado."))
        return {"type": "ir.actions.act_url", "url": f"/sp_banco/original/{self.id}", "target": "self"}

    def _sp_original_en_claro(self):
        """Contenido del extracto original descifrado (solo Contabilidad)."""
        self.ensure_one()
        if not self.env.user.has_group("sp_recepcion.group_sp_responsable"):
            raise UserError(_("Solo Contabilidad descarga los extractos originales."))
        datos = self.original_id.sudo().raw
        datos = getattr(datos, "content", datos)
        try:
            claro = cifrado.descifrar_archivo(datos)
        except cifrado.SinClave as e:
            raise UserError(str(e)) from e
        if self.huella and hashlib.sha256(claro).hexdigest() != self.huella:
            raise UserError(_("El original no coincide con su huella: avise a quien administra el sistema."))
        return self.name, claro

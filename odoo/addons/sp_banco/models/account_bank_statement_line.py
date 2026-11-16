"""Movimientos bancarios: propuestas de conciliación explicadas y validación por Contabilidad.

Reglas deterministas adaptadas de Sistema Propio (referencia/SistemaPropio/apps/api/app/bank/matcher.py). Cada
regla es verificable a mano y deja su explicación. La primera que encuentra un candidato ÚNICO gana. Si no hay
candidato único, el movimiento queda como excepción con su motivo. NUNCA se concilia sola una propuesta: siempre la
valida Contabilidad.
"""
import itertools
import re
from datetime import timedelta

from odoo import Command, _, api, fields, models
from odoo.exceptions import AccessError, UserError

G_RESPONSABLE = "sp_recepcion.group_sp_responsable"

KW_TRASPASO = re.compile(r"\bTRASPASO", re.I)
KW_BIZUM = re.compile(r"\bBIZUM\b", re.I)
KW_TPV = re.compile(r"\b(TPV|DATAFONO|DATÁFONO|LIQUIDACI[OÓ]N TARJETAS|LIQ\.? TARJETAS|COMERCIO)\b", re.I)
KW_COMISION = re.compile(r"\bCOMISI[OÓ]N", re.I)
# Referencias que el despacho da a sus clientes: nº de factura (CIT/…, EXP/…), justificante (REC-…) o cobro (P…/…).
REF_FACTURA = re.compile(r"\b((?:R?CIT|R?EXP|INV)/\d{4}/\d{4,6})\b", re.I)
REF_JUSTIFICANTE = re.compile(r"\b(REC-[A-Z]{2,5}-\d{4}-\d{6})\b", re.I)
CATEGORIAS = [
    (re.compile(r"\b(TGSS|SEGURIDAD SOCIAL|SEG\.? SOCIAL)\b", re.I), "Seguridad Social"),
    (re.compile(r"\b(AEAT|HACIENDA|AGENCIA TRIBUTARIA|MODELO \d{3})\b", re.I), "Impuestos"),
    (re.compile(r"\bN[OÓ]MINA", re.I), "Nómina"),
    (re.compile(r"\bALQUILER\b", re.I), "Alquiler"),
    (KW_COMISION, "Comisión bancaria"),
    (KW_TPV, "TPV"), (KW_BIZUM, "Bizum"), (KW_TRASPASO, "Traspaso"),
]
ESTADOS = [
    ("pendiente", "Pendiente"),
    ("propuesto", "Propuesta para validar"),
    ("excepcion", "Excepción: revisar a mano"),
    ("conciliado", "Conciliado"),
    ("traspaso", "Traspaso entre cuentas propias"),
    ("justificado", "Contabilizado en una cuenta"),
    ("ignorado", "Ignorado"),
]


def eur(v):
    return f"{v:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    sp_ext_id = fields.Char("Identificador estable", index=True, copy=False, readonly=True,
                            help="El del banco o una huella de los datos: reimportar no duplica.")
    sp_referencia = fields.Char("Referencia del banco", readonly=True)
    sp_fecha_valor = fields.Date("Fecha valor", readonly=True)
    sp_importacion_id = fields.Many2one("sp.banco.importacion", "Importación", readonly=True)
    sp_estado = fields.Selection(ESTADOS, "Estado de conciliación", default="pendiente", index=True)
    sp_regla = fields.Char("Regla", readonly=True)
    sp_explicacion = fields.Text("Por qué se propone / qué falta", readonly=True)
    sp_categoria = fields.Char("Categoría sugerida", readonly=True)
    sp_prioridad = fields.Selection([("alta", "Alta"), ("media", "Media")], readonly=True)
    sp_propuesta_aml_ids = fields.Many2many("account.move.line", "sp_banco_propuesta_rel", "st_line_id", "aml_id",
                                            string="Apuntes propuestos", readonly=True)
    sp_contrapartida_id = fields.Many2one("account.bank.statement.line", "Movimiento contrario (traspaso)", readonly=True)
    sp_rechazadas_aml_ids = fields.Many2many("account.move.line", "sp_banco_rechazada_rel", "st_line_id", "aml_id",
                                             string="Propuestas rechazadas", readonly=True)
    sp_nota = fields.Text("Nota de Contabilidad",
                          help="Obligatoria para rechazar una propuesta, ignorar un movimiento o contabilizarlo en una cuenta.")
    sp_cuenta_id = fields.Many2one("account.account", "Contabilizar en la cuenta",
                                   help="Para cargos o abonos sin factura ni cobro (comisiones, Seguridad Social…).")
    sp_validado_por = fields.Many2one("res.users", "Validado por", readonly=True)
    sp_ajuste_importe = fields.Monetary("Diferencia", currency_field="currency_id", readonly=True,
                                        help="Importe del movimiento que no cubren los apuntes propuestos (p. ej. la "
                                             "comisión que el banco descuenta de una liquidación de TPV).")
    sp_ajuste_cuenta_id = fields.Many2one("account.account", "Cuenta de la diferencia", readonly=True)
    sp_manual_aml_ids = fields.Many2many(
        "account.move.line", "sp_banco_manual_rel", "st_line_id", "aml_id", string="Elegir apuntes a mano",
        domain="[('company_id', '=', company_id), ('parent_state', '=', 'posted'), ('reconciled', '=', False), "
               "('account_id.reconcile', '=', True), ('amount_residual', '!=', 0), ('move_id.statement_line_id', '=', False)]",
        help="Cobros, pagos o facturas pendientes que corresponden a este movimiento cuando el sistema no los ha "
             "encontrado o ha propuesto otros.")

    _sp_ext_unico = models.UniqueIndex("(journal_id, sp_ext_id) WHERE sp_ext_id IS NOT NULL")

    # ------------------------------------------------------------------------------------------- candidatos
    def _sp_ocupados(self):
        """Apuntes ya propuestos a otro movimiento abierto."""
        otros = self.search([("id", "not in", self.ids), ("sp_estado", "=", "propuesto")])
        return otros.sp_propuesta_aml_ids

    def _sp_lineas_pago(self, tipo, importe=None, alrededor=None, dias=5, journal=None):
        """Apuntes pendientes de los cobros (tipo inbound) o pagos (outbound) registrados por esta cuenta."""
        dominio = [("journal_id", "=", (journal or self.journal_id).id), ("payment_type", "=", tipo),
                   ("state", "=", "paid")]
        if importe is not None:
            dominio.append(("amount", "=", importe))
        if alrededor:
            dominio += [("date", ">=", alrededor - timedelta(days=dias)), ("date", "<=", alrededor + timedelta(days=dias))]
        pagos = self.env["account.payment"].search(dominio, order="date, id")
        lineas = self.env["account.move.line"]
        for p in pagos:
            lineas |= p.move_id.line_ids.filtered(
                lambda l, p=p: l.account_id == p.outstanding_account_id and not l.reconciled and l.amount_residual)
        return lineas - self._sp_ocupados() - self.sp_rechazadas_aml_ids

    @staticmethod
    def _sp_texto(lineas):
        partes = []
        for l in lineas:
            doc = l.payment_id.sp_justificante_numero if "sp_justificante_numero" in l.payment_id._fields else False
            partes.append(f"{doc or l.move_id.name} · {l.partner_id.name or '—'} · {eur(abs(l.amount_residual))} "
                          f"({l.date:%d/%m/%Y})")
        return "; ".join(partes)

    # ------------------------------------------------------------------------------------------- reglas
    def _sp_regla_traspaso(self):
        texto = self.payment_ref or ""
        otros = self.search([("id", "!=", self.id), ("company_id", "=", self.company_id.id),
                             ("journal_id", "!=", self.journal_id.id), ("journal_id.type", "=", "bank"),
                             ("amount", "=", -self.amount), ("is_reconciled", "=", False),
                             ("sp_estado", "in", ("pendiente", "excepcion", "propuesto")),
                             ("date", ">=", self.date - timedelta(days=3)), ("date", "<=", self.date + timedelta(days=3))])
        # Un movimiento ya propuesto solo sirve si su propia propuesta es este mismo traspaso (o aún no tiene pareja).
        otros = otros.filtered(lambda o: (KW_TRASPASO.search(texto) or KW_TRASPASO.search(o.payment_ref or ""))
                               and (o.sp_estado != "propuesto" or o.sp_contrapartida_id in (self, self.browse())))
        if not otros:
            if KW_TRASPASO.search(texto):
                return ("excepcion", "traspaso_sin_contrapartida",
                        _("Parece un traspaso entre cuentas propias de %s, pero no aparece el movimiento contrario en "
                          "otra cuenta (¿falta importar su extracto?). Un traspaso nunca es un ingreso.", eur(self.amount)),
                        {"categoria": "Traspaso"})
            return None
        if len(otros) > 1:
            return ("excepcion", "traspaso_ambiguo",
                    _("Hay %s movimientos contrarios posibles para este traspaso. Elija el correcto a mano.", len(otros)), {})
        o = otros
        return ("propuesto", "traspaso",
                _("Traspaso entre cuentas propias: %(a)s el %(f1)s y %(b)s el %(f2)s en «%(c)s». No es un ingreso.",
                  a=eur(self.amount), f1=self.date.strftime("%d/%m/%Y"), b=eur(o.amount),
                  f2=o.date.strftime("%d/%m/%Y"), c=o.journal_id.name), {"contrapartida": o})

    def _sp_regla_referencia(self):
        if self.amount <= 0:
            return None
        texto = f"{self.payment_ref or ''} {self.sp_referencia or ''}".upper()
        # La Norma 43 trocea el concepto en tramos de 38 caracteres: una referencia puede llegar partida por un
        # espacio («EXP/2026/0000 3»). Se busca también en el texto sin espacios entre cifras o barras.
        texto += " " + re.sub(r"(?<=[\d/])\s+(?=[\d/])", "", texto)
        facturas = {m.upper() for m in REF_FACTURA.findall(texto)}
        justificantes = {m.upper() for m in REF_JUSTIFICANTE.findall(texto)}
        facturas = {f for f in facturas if not any(o != f and o.startswith(f) for o in facturas)}  # trozos sueltos fuera
        if not facturas and not justificantes:
            return None
        lineas = self.env["account.move.line"]
        if justificantes and "sp_justificante_numero" in self.env["account.payment"]._fields:
            pagos = self.env["account.payment"].search([("sp_justificante_numero", "in", list(justificantes)),
                                                        ("company_id", "=", self.company_id.id)])
            for p in pagos:
                lineas |= p.move_id.line_ids.filtered(
                    lambda l, p=p: l.account_id == p.outstanding_account_id and not l.reconciled)
        if facturas:
            fact = self.env["account.move"].search([("name", "in", list(facturas)), ("state", "=", "posted"),
                                                    ("company_id", "=", self.company_id.id)])
            # Cobros ya registrados contra esas facturas (pendientes de conciliar) o, si no hay, la propia factura.
            for f in fact:
                pagos_f = self.env["account.payment"].search([("reconciled_invoice_ids", "in", f.ids)])
                lp = self.env["account.move.line"]
                for p in pagos_f:
                    lp |= p.move_id.line_ids.filtered(
                        lambda l, p=p: l.account_id == p.outstanding_account_id and not l.reconciled)
                lineas |= lp or f.line_ids.filtered(
                    lambda l: l.account_id.account_type == "asset_receivable" and not l.reconciled)
        lineas -= self._sp_ocupados() | self.sp_rechazadas_aml_ids
        lineas = lineas.filtered(lambda l: 0 < l.amount_residual <= self.amount + 0.001)
        refs = ", ".join(sorted(facturas | justificantes))
        for n in range(1, min(4, len(lineas)) + 1):
            combos = [c for c in itertools.combinations(lineas, n)
                      if self.currency_id.is_zero(sum(x.amount_residual for x in c) - self.amount)]
            if len(combos) == 1:
                c = self.env["account.move.line"].concat(*combos[0])
                return ("propuesto", "referencia",
                        _("El concepto trae la referencia %(r)s y %(q)s suma exactamente %(i)s: %(t)s.", r=refs,
                          q=_("el apunte pendiente") if n == 1 else _("%s apuntes pendientes", n), i=eur(self.amount),
                          t=self._sp_texto(c)), {"lineas": c})
            if len(combos) > 1:
                return ("excepcion", "referencia_ambigua",
                        _("%(r)s: varias combinaciones suman %(i)s. Elija a mano.", r=refs, i=eur(self.amount)), {})
        return ("excepcion", "cobro_no_registrado",
                _("Ha entrado %(i)s con la referencia %(r)s, pero no hay cobros ni facturas pendientes que lo justifiquen. "
                  "Registre el cobro o revise la referencia.", i=eur(self.amount), r=refs), {"prioridad": "alta"})

    def _sp_regla_bizum(self):
        if self.amount <= 0 or not KW_BIZUM.search(self.payment_ref or ""):
            return None
        lineas = self._sp_lineas_pago("inbound", self.amount, self.date, dias=3)
        if len(lineas) == 1:
            return ("propuesto", "bizum", _("Bizum de %(i)s y un único cobro del mismo importe en ±3 días: %(t)s.",
                                            i=eur(self.amount), t=self._sp_texto(lineas)), {"lineas": lineas})
        if len(lineas) > 1:
            return ("excepcion", "bizum_ambiguo", _("Hay %(n)s cobros de %(i)s en esas fechas: %(t)s. Elija el correcto.",
                                                    n=len(lineas), i=eur(self.amount), t=self._sp_texto(lineas)), {})
        return None

    def _sp_regla_tpv(self):
        if self.amount <= 0 or not KW_TPV.search(self.payment_ref or ""):
            return None
        lineas = self._sp_lineas_pago("inbound", None, self.date, dias=4).filtered(lambda l: l.date <= self.date)
        por_dia = {}
        for l in lineas:
            por_dia.setdefault(l.date, self.env["account.move.line"])
            por_dia[l.date] |= l
        encontrados = [(d, ls) for d, ls in por_dia.items()
                       if self.currency_id.is_zero(sum(ls.mapped("amount_residual")) - self.amount)]
        if len(encontrados) == 1:
            d, ls = encontrados[0]
            return ("propuesto", "tpv", _("Liquidación de TPV de %(i)s = %(n)s cobros con tarjeta del %(d)s.",
                                          i=eur(self.amount), n=len(ls), d=d.strftime("%d/%m/%Y")), {"lineas": ls})
        if len(encontrados) > 1:
            return ("excepcion", "tpv_ambiguo", _("Varios días de cobros con tarjeta cuadran con este abono. Elija a mano."), {})
        # El banco suele liquidar el TPV descontando su comisión: abono = cobros del día − comisión (hasta un 3 %).
        con_comision = [(d, ls, sum(ls.mapped("amount_residual")) - self.amount) for d, ls in por_dia.items()]
        con_comision = [(d, ls, c) for d, ls, c in con_comision if 0 < c <= round(0.03 * (c + self.amount), 2)]
        cuenta = self._sp_cuenta_comision()
        if len(con_comision) == 1 and cuenta:
            d, ls, c = con_comision[0]
            bruto = c + self.amount
            return ("propuesto", "tpv_comision",
                    _("Liquidación de TPV de %(i)s = %(n)s cobros con tarjeta del %(d)s (%(b)s) menos %(c)s de comisión "
                      "del banco (%(p)s %%), que va a la cuenta %(cu)s.", i=eur(self.amount), n=len(ls),
                      d=d.strftime("%d/%m/%Y"), b=eur(bruto), c=eur(c), p=f"{100 * c / bruto:.2f}".replace(".", ","),
                      cu=cuenta.code), {"lineas": ls, "ajuste": (cuenta, -c)})
        return ("excepcion", "tpv_sin_cuadre",
                _("Liquidación de TPV de %s que no cuadra con los cobros registrados en esta cuenta. Revise los cobros con "
                  "tarjeta de esos días (y si el banco ha descontado comisión).", eur(self.amount)),
                {"categoria": "TPV", "prioridad": "alta"})

    def _sp_cuenta_comision(self):
        """Cuenta de servicios bancarios (626 del PGC) de la compañía del movimiento."""
        Cuenta = self.env["account.account"].with_company(self.company_id)
        return (Cuenta.search([("code", "=", "626000")], limit=1)
                or Cuenta.search([("code", "=like", "626%")], limit=1))

    def _sp_regla_devolucion(self):
        if self.amount >= 0 or "sp.devolucion" not in self.env:
            return None
        Dev = self.env["sp.devolucion"]
        pagadas = Dev.search([("estado", "=", "pagada"), ("importe", "=", -self.amount),
                              ("pago_id.journal_id", "=", self.journal_id.id)])
        lineas = self.env["account.move.line"]
        for d in pagadas:
            p = d.pago_id
            if abs((p.date - self.date).days) <= 5:
                lineas |= p.move_id.line_ids.filtered(
                    lambda l, p=p: l.account_id == p.outstanding_account_id and not l.reconciled)
        lineas -= self._sp_ocupados() | self.sp_rechazadas_aml_ids
        if len(lineas) == 1:
            dev = pagadas.filtered(lambda d: d.pago_id == lineas.payment_id)[:1]
            return ("propuesto", "devolucion", _("Devolución %(d)s pagada de %(i)s a %(c)s (%(f)s).", d=dev.name,
                                                 i=eur(-self.amount), c=dev.partner_id.name,
                                                 f=lineas.date.strftime("%d/%m/%Y")), {"lineas": lineas})
        if len(lineas) > 1:
            return ("excepcion", "devolucion_ambigua",
                    _("%(n)s devoluciones pagadas de %(i)s en esas fechas. Elija la correcta.", n=len(lineas), i=eur(-self.amount)), {})
        if Dev.search_count([("estado", "=", "aprobada"), ("importe", "=", -self.amount)]):
            return ("excepcion", "devolucion_sin_pago",
                    _("Sale %s y hay una devolución APROBADA de ese importe todavía sin pago registrado. Si es ella, "
                      "registre el pago en la devolución y vuelva a proponer.", eur(-self.amount)), {"prioridad": "alta"})
        return None

    def _sp_regla_proveedor(self):
        """Pago a proveedor: un pago registrado por esta cuenta del mismo importe (±5 días), o una factura de proveedor
        pendiente del mismo importe cuyo proveedor o número aparece en el concepto."""
        if self.amount >= 0:
            return None
        lineas = self._sp_lineas_pago("outbound", -self.amount, self.date, dias=5)
        if len(lineas) == 1:
            return ("propuesto", "pago_registrado", _("Pago de %(i)s registrado por esta cuenta en ±5 días: %(t)s.",
                                                      i=eur(-self.amount), t=self._sp_texto(lineas)), {"lineas": lineas})
        if len(lineas) > 1:
            return ("excepcion", "pago_ambiguo", _("%(n)s pagos de %(i)s en esas fechas: %(t)s. Elija el correcto.",
                                                   n=len(lineas), i=eur(-self.amount), t=self._sp_texto(lineas)), {})
        texto = (f"{self.payment_ref or ''} {self.sp_referencia or ''} {self.partner_name or ''}").upper()
        facturas = self.env["account.move"].search([
            ("move_type", "=", "in_invoice"), ("state", "=", "posted"), ("company_id", "=", self.company_id.id),
            ("payment_state", "in", ("not_paid", "partial")), ("amount_residual", "=", -self.amount)])
        candidatas = []
        for f in facturas:
            palabras = [w for w in re.findall(r"[A-ZÁÉÍÓÚÑ]{4,}", (f.partner_id.name or "").upper())
                        if w not in ("DEMO", "SOCIEDAD", "LIMITADA", "FICTICIO", "FICTICIOS")]
            nombrada = any(w in texto for w in palabras) or (f.ref and f.ref.upper() in texto)
            vence = f.invoice_date_due or f.invoice_date
            if nombrada and vence and -10 <= (self.date - vence).days <= 30:
                candidatas.append(f)
        if len(candidatas) == 1:
            f = candidatas[0]
            lineas = f.line_ids.filtered(lambda l: l.account_id.account_type == "liability_payable" and not l.reconciled)
            lineas -= self._sp_ocupados() | self.sp_rechazadas_aml_ids
            if lineas:
                return ("propuesto", "factura_proveedor",
                        _("Pago de la factura %(n)s de %(p)s (%(i)s): mismo importe y el proveedor aparece en el concepto.",
                          n=f.ref or f.name, p=f.partner_id.name, i=eur(f.amount_total)), {"lineas": lineas})
        if len(candidatas) > 1:
            return ("excepcion", "factura_ambigua", _("%s facturas del mismo proveedor e importe. Elija la correcta.",
                                                      len(candidatas)), {})
        return None

    def _sp_regla_importe_fecha(self):
        if self.amount <= 0:
            return None
        lineas = self._sp_lineas_pago("inbound", self.amount, self.date, dias=5)
        if len(lineas) == 1:
            ordenante = f" («{self.partner_name}»)" if self.partner_name else ""
            return ("propuesto", "importe_fecha",
                    _("Transferencia SIN referencia: un único cobro de %(i)s registrado en ±5 días (%(t)s). Compruebe el "
                      "ordenante%(o)s antes de validar.", i=eur(self.amount), t=self._sp_texto(lineas), o=ordenante),
                    {"lineas": lineas})
        if len(lineas) > 1:
            return ("excepcion", "importe_ambiguo", _("%(n)s cobros de %(i)s en esas fechas: %(t)s. Elija el correcto.",
                                                      n=len(lineas), i=eur(self.amount), t=self._sp_texto(lineas)), {})
        return None

    def _sp_reglas(self):
        """Reglas en orden: gana la primera que decide. Otros módulos (sp_facturacion) insertan las suyas."""
        return [self._sp_regla_traspaso, self._sp_regla_referencia, self._sp_regla_bizum, self._sp_regla_tpv,
                self._sp_regla_devolucion, self._sp_regla_proveedor, self._sp_regla_importe_fecha]

    def _sp_evaluar(self):
        self.ensure_one()
        for regla in self._sp_reglas():
            r = regla()
            if r is not None:
                return r
        texto = f"{self.payment_ref or ''} {self.sp_referencia or ''}"
        cat = next((c for rx, c in CATEGORIAS if rx.search(texto)), None)
        if self.amount > 0:
            return ("excepcion", "ingreso_sin_identificar",
                    _("Ha entrado %s y no hay cobro registrado que lo justifique. Identifique al cliente y registre el "
                      "cobro, o contabilícelo en una cuenta con su motivo.", eur(self.amount)),
                    {"categoria": cat, "prioridad": "alta"})
        return ("excepcion", "cargo_sin_justificar",
                _("Ha salido %(i)s%(c)s. Si es un proveedor, registre su factura y vuelva a proponer; si no, "
                  "contabilícelo en su cuenta con un motivo.", i=eur(-self.amount),
                  c=f" (parece: {cat})" if cat else ""), {"categoria": cat, "prioridad": "media" if cat else "alta"})

    def _sp_valores_reinicio(self):
        """Lo que se borra antes de volver a proponer (otros módulos añaden sus campos)."""
        return {"sp_estado": "pendiente", "sp_propuesta_aml_ids": [Command.clear()], "sp_contrapartida_id": False,
                "sp_ajuste_importe": 0.0, "sp_ajuste_cuenta_id": False}

    def _sp_proponer(self):
        """Agente de conciliación: deja propuestas y excepciones. No concilia nada."""
        # El agente lee cobros, facturas y devoluciones de todo el despacho para proponer (no cambia nada de ellos):
        # se ejecuta como superusuario técnico. Validar sí exige el grupo de Contabilidad.
        for st in self.sudo().filtered(lambda s: not s.is_reconciled and s.sp_estado in ("pendiente", "excepcion", "propuesto")):
            st.write(st._sp_valores_reinicio())
            estado, regla, explicacion, extra = st._sp_evaluar()
            cuenta_ajuste, ajuste = extra.get("ajuste", (self.env["account.account"], 0.0))
            st.write({"sp_ajuste_importe": ajuste, "sp_ajuste_cuenta_id": cuenta_ajuste.id or False,"sp_estado": estado, "sp_regla": regla, "sp_explicacion": explicacion,
                      "sp_categoria": extra.get("categoria"), "sp_prioridad": extra.get("prioridad", "media"),
                      "sp_propuesta_aml_ids": [Command.set(extra.get("lineas", self.env["account.move.line"]).ids)],
                      "sp_contrapartida_id": extra.get("contrapartida", self.browse()).id or False,
                      **extra.get("vals", {})})
        return True

    def action_sp_proponer(self):
        self._sp_exigir()
        return self._sp_proponer()

    @api.model
    def _sp_cron_proponer(self):
        self.search([("is_reconciled", "=", False), ("sp_estado", "in", ("pendiente", "excepcion"))])._sp_proponer()

    # ------------------------------------------------------------------------------------------- validar
    def _sp_exigir(self):
        if not self.env.user.has_group(G_RESPONSABLE):
            raise AccessError(_("Solo Contabilidad valida, rechaza o justifica movimientos bancarios."))

    def _sp_reemplazar_contrapartida(self, contrapartidas):
        """Sustituye la línea transitoria del movimiento por las contrapartidas [(cuenta, empresa, saldo, texto)] y
        devuelve las líneas creadas (técnica de account_reconcile_oca de la OCA)."""
        self.ensure_one()
        _liquidez, transitoria, otras = self._seek_for_lines()
        move = self.move_id
        nuevas = self.env["account.move.line"]
        ctx = dict(skip_account_move_synchronization=True, force_delete=True, skip_invoice_sync=True,
                   skip_readonly_check=True)
        with move._check_balanced({"records": move, "self": move}):
            move.with_context(**ctx).write({"line_ids": [Command.delete(l.id) for l in transitoria + otras]})
            for cuenta, empresa, saldo, texto in contrapartidas:
                nuevas |= self.env["account.move.line"].with_context(check_move_validity=False, skip_invoice_sync=True).create({
                    "move_id": move.id, "account_id": cuenta.id, "partner_id": empresa.id if empresa else False,
                    "name": texto, "debit": saldo if saldo > 0 else 0.0, "credit": -saldo if saldo < 0 else 0.0})
        return nuevas

    def action_sp_validar(self):
        self._sp_exigir()
        for st in self:
            if st.sp_estado != "propuesto":
                raise UserError(_("Solo se validan propuestas."))
            if st.sp_regla == "traspaso":
                o = st.sp_contrapartida_id
                if not o or o.is_reconciled:
                    raise UserError(_("El movimiento contrario ya no está disponible. Vuelva a proponer."))
                puente = st.company_id.transfer_account_id
                if not puente:
                    raise UserError(_("La compañía no tiene cuenta de traspasos internos."))
                a = st._sp_reemplazar_contrapartida([(puente, False, -st.amount, st.payment_ref or _("Traspaso"))])
                b = o._sp_reemplazar_contrapartida([(puente, False, -o.amount, o.payment_ref or _("Traspaso"))])
                (a | b).reconcile()
                st.write({"sp_estado": "traspaso", "sp_validado_por": self.env.uid})
                o.write({"sp_estado": "traspaso", "sp_validado_por": self.env.uid, "sp_regla": "traspaso",
                         "sp_contrapartida_id": st.id, "sp_explicacion": st.sp_explicacion,
                         "sp_propuesta_aml_ids": [Command.clear()]})
                continue
            objetivo = st.sp_propuesta_aml_ids
            if not objetivo or any(l.reconciled for l in objetivo):
                raise UserError(_("Los apuntes propuestos ya no están pendientes. Vuelva a proponer."))
            if st.sp_regla == "manual_parcial":
                # Pago parcial de un único apunte: se concilia por el importe del movimiento y el resto sigue pendiente.
                if not st._sp_es_parcial(objetivo):
                    raise UserError(_("El apunte ya no admite este pago parcial. Vuelva a elegir."))
                contrapartidas = [(objetivo.account_id, objetivo.partner_id, -st.amount, objetivo.move_id.name)]
            else:
                ajuste = st.sp_ajuste_importe or 0.0
                if not st.currency_id.is_zero(sum(objetivo.mapped("amount_residual")) + ajuste - st.amount):
                    raise UserError(_("Los apuntes propuestos no suman el importe del movimiento."))
                if ajuste and not st.sp_ajuste_cuenta_id:
                    raise UserError(_("Falta la cuenta de la diferencia."))
                contrapartidas = [(l.account_id, l.partner_id, -l.amount_residual, l.move_id.name) for l in objetivo]
                if ajuste:
                    contrapartidas.append((st.sp_ajuste_cuenta_id, False, -ajuste,
                                           _("Comisión del TPV") if st.sp_regla == "tpv_comision"
                                           else (st.sp_nota or "").strip()[:120] or _("Diferencia")))
            nuevas = st._sp_reemplazar_contrapartida(contrapartidas)
            for nueva, l in zip(nuevas, objetivo):
                (nueva | l).reconcile()
            st.write({"sp_estado": "conciliado", "sp_validado_por": self.env.uid, "sp_manual_aml_ids": [Command.clear()]})
        return True

    def _sp_es_parcial(self, lineas):
        return (len(lineas) == 1 and lineas.amount_residual * self.amount > 0
                and abs(self.amount) < abs(lineas.amount_residual) - 0.001)

    def action_sp_elegir_a_mano(self):
        """Contabilidad elige los apuntes. Si suman el movimiento, propuesta normal; si es uno solo y mayor, pago
        parcial; si no cuadran, la diferencia va a la cuenta elegida con su motivo. Después se valida igual."""
        self._sp_exigir()
        for st in self:
            if st.is_reconciled or st.sp_estado not in ("pendiente", "excepcion", "propuesto"):
                raise UserError(_("Este movimiento ya está cerrado."))
            lineas = st.sp_manual_aml_ids
            if not lineas:
                raise UserError(_("Elija al menos un apunte en «Elegir apuntes a mano»."))
            if lineas.filtered("reconciled"):
                raise UserError(_("Alguno de los apuntes elegidos ya está conciliado."))
            if lineas & st._sp_ocupados():
                raise UserError(_("Alguno de los apuntes elegidos está propuesto para otro movimiento."))
            total = sum(lineas.mapped("amount_residual"))
            diferencia = st.currency_id.round(st.amount - total)
            vals = {"sp_estado": "propuesto", "sp_propuesta_aml_ids": [Command.set(lineas.ids)],
                    "sp_contrapartida_id": False, "sp_ajuste_importe": 0.0, "sp_ajuste_cuenta_id": False,
                    "sp_prioridad": "media"}
            usuario = self.env.user.name
            if st.currency_id.is_zero(diferencia):
                vals.update(sp_regla="manual", sp_explicacion=_("Elegido a mano por %(u)s: %(t)s.", u=usuario,
                                                                 t=st._sp_texto(lineas)))
            elif st._sp_es_parcial(lineas):
                vals.update(sp_regla="manual_parcial", sp_explicacion=_(
                    "Pago PARCIAL elegido a mano por %(u)s: %(i)s de %(t)s. Quedarán pendientes %(q)s.", u=usuario,
                    i=eur(abs(st.amount)), t=st._sp_texto(lineas), q=eur(abs(total) - abs(st.amount))))
            else:
                if not st.sp_cuenta_id:
                    raise UserError(_("Los apuntes elegidos suman %(t)s y el movimiento es de %(i)s. Elija en «Contabilizar "
                                      "en la cuenta» dónde va la diferencia de %(d)s y escriba el motivo.",
                                      t=eur(total), i=eur(st.amount), d=eur(diferencia)))
                st._sp_exigir_nota()
                vals.update(sp_regla="manual_diferencia", sp_ajuste_importe=diferencia, sp_ajuste_cuenta_id=st.sp_cuenta_id.id,
                            sp_explicacion=_("Elegido a mano por %(u)s: %(t)s. Diferencia de %(d)s a la cuenta %(c)s: %(n)s.",
                                             u=usuario, t=st._sp_texto(lineas), d=eur(diferencia),
                                             c=st.sp_cuenta_id.code, n=st.sp_nota.strip()))
            st.write(vals)
        return True

    def _sp_exigir_nota(self, minimo=10):
        for st in self:
            if len((st.sp_nota or "").strip()) < minimo:
                raise UserError(_("Escriba en «Nota de Contabilidad» el motivo (mínimo %s caracteres).", minimo))

    def action_sp_rechazar(self):
        self._sp_exigir()
        self._sp_exigir_nota()
        for st in self.filtered(lambda s: s.sp_estado == "propuesto"):
            st.write({"sp_rechazadas_aml_ids": [Command.link(i) for i in st.sp_propuesta_aml_ids.ids]})
            st.move_id.message_post(body=_("Propuesta rechazada: %s", st.sp_nota))
            st.write({"sp_estado": "pendiente"})
            st._sp_proponer()
        return True

    def action_sp_contabilizar_en_cuenta(self):
        """Cargo o abono sin factura ni cobro (comisión, Seguridad Social…): a la cuenta elegida, con motivo."""
        self._sp_exigir()
        self._sp_exigir_nota()
        for st in self:
            if st.is_reconciled:
                raise UserError(_("El movimiento ya está conciliado."))
            if not st.sp_cuenta_id:
                raise UserError(_("Elija la cuenta en «Contabilizar en la cuenta»."))
            st._sp_reemplazar_contrapartida([(st.sp_cuenta_id, st.partner_id, -st.amount, st.sp_nota.strip()[:120])])
            st.write({"sp_estado": "justificado", "sp_validado_por": self.env.uid})
        return True

    def action_sp_ignorar(self):
        self._sp_exigir()
        self._sp_exigir_nota()
        self.filtered(lambda s: not s.is_reconciled).write({"sp_estado": "ignorado", "sp_validado_por": self.env.uid})
        return True

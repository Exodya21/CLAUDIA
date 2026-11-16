"""Exportación de los movimientos bancarios a CSV para la gestoría (documento 19 §3.3)."""
import base64
import csv
import io

from odoo import _, fields, models
from odoo.exceptions import UserError

from ..models.account_bank_statement_line import ESTADOS


def importe(v):
    return f"{v:.2f}".replace(".", ",")


class SpBancoExportar(models.TransientModel):
    _name = "sp.banco.exportar"
    _description = "Exportar movimientos bancarios para la gestoría"

    fecha_desde = fields.Date("Desde", required=True)
    fecha_hasta = fields.Date("Hasta", required=True)
    journal_ids = fields.Many2many("account.journal", string="Cuentas", domain="[('type', '=', 'bank')]",
                                   help="Vacío: todas las cuentas bancarias.")
    solo_cerrados = fields.Boolean("Solo movimientos cerrados", help="Conciliados, traspasos, contabilizados en una "
                                   "cuenta o ignorados. Lo abierto se exporta con su estado si no se marca.")

    def _sp_filas(self):
        dominio = [("journal_id.type", "=", "bank"), ("date", ">=", self.fecha_desde), ("date", "<=", self.fecha_hasta),
                   ("company_id", "in", self.env.companies.ids)]
        if self.journal_ids:
            dominio.append(("journal_id", "in", self.journal_ids.ids))
        if self.solo_cerrados:
            dominio.append(("sp_estado", "in", ("conciliado", "traspaso", "justificado", "ignorado")))
        estados = dict(ESTADOS)
        for st in self.env["account.bank.statement.line"].search(dominio, order="journal_id, date, id"):
            liquidez, _transitoria, otras = st._seek_for_lines()
            contrapartida = otras or _transitoria
            documentos = (contrapartida.matched_debit_ids.debit_move_id.move_id
                          | contrapartida.matched_credit_ids.credit_move_id.move_id)
            yield [st.date.strftime("%d/%m/%Y"), st.sp_fecha_valor and st.sp_fecha_valor.strftime("%d/%m/%Y") or "",
                   st.journal_id.name, st.payment_ref or "", st.partner_name or st.partner_id.name or "",
                   importe(st.amount), estados.get(st.sp_estado, st.sp_estado or ""), st.sp_regla or "",
                   " | ".join(f"{l.account_id.code} {importe(l.balance)}" for l in contrapartida),
                   " | ".join(documentos.mapped("name")), (st.sp_nota or "").replace("\n", " "),
                   st.sp_validado_por.name or "", st.move_id.name or ""]

    def action_exportar(self):
        if not self.env.user.has_group("sp_recepcion.group_sp_responsable"):
            raise UserError(_("Solo Contabilidad exporta los movimientos bancarios."))
        if self.fecha_hasta < self.fecha_desde:
            raise UserError(_("La fecha final es anterior a la inicial."))
        salida = io.StringIO()
        w = csv.writer(salida, delimiter=";", quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
        w.writerow(["Fecha", "Fecha valor", "Cuenta", "Concepto", "Ordenante o beneficiario", "Importe", "Estado",
                    "Regla", "Contrapartida (cuenta importe)", "Documentos conciliados", "Nota de Contabilidad",
                    "Validado por", "Asiento"])
        n = 0
        for fila in self._sp_filas():
            w.writerow(fila)
            n += 1
        if not n:
            raise UserError(_("No hay movimientos en ese periodo."))
        nombre = f"movimientos_banco_{self.fecha_desde:%Y%m%d}_{self.fecha_hasta:%Y%m%d}.csv"
        # UTF-8 con BOM: Excel en español lo abre con tildes y separador «;» sin preguntar.
        adjunto = self.env["ir.attachment"].create({
            "name": nombre, "raw": ("﻿" + salida.getvalue()).encode("utf-8"), "mimetype": "text/csv"})
        return {"type": "ir.actions.act_url", "url": f"/web/content/{adjunto.id}?download=true", "target": "self"}

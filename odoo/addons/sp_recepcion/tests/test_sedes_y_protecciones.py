# Cada recepción solo ve su sede; refuerzos en la base de datos; apuntes de caja de días validados. DATOS FICTICIOS.
import psycopg2

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import SpRecepcionCommon


@tagged("post_install", "-at_install", "sp_recepcion")
class TestSedesYProtecciones(SpRecepcionCommon):

    def test_recepcion_solo_ve_su_sede(self):
        c_bcn = self._cobro(50)
        c_bcn.action_post()
        c_mad = self._cobro(60, usuario=self.recepcion_mad, journal_id=self.caja_mad.id)
        c_mad.action_post()
        Pay = self.env["account.payment"]
        self.assertEqual(Pay.with_user(self.recepcion).search([("sp_sede_id", "!=", False)]), c_bcn)
        self.assertEqual(Pay.with_user(self.recepcion_mad).search([("sp_sede_id", "!=", False)]), c_mad)
        self.assertEqual(Pay.with_user(self.conta1).search([("sp_sede_id", "!=", False)]), c_bcn | c_mad,
                         "Contabilidad ve los cobros de todas las sedes")
        with self.assertRaises(AccessError):
            c_mad.with_user(self.recepcion).read(["amount"])

    def test_recepcion_no_registra_en_otra_sede(self):
        with self.assertRaises(AccessError):
            self._cobro(50, sp_sede_id=self.sede_mad.id, journal_id=self.caja_mad.id)
        with self.assertRaises(AccessError):
            self._cierre(0, sede=self.sede_mad)

    def test_varias_sedes(self):
        self.recepcion.sp_sede_ids = [(4, self.sede_mad.id)]
        c = self._cobro(70, sp_sede_id=self.sede_mad.id, journal_id=self.caja_mad.id)
        c.action_post()
        self.assertTrue(c.sp_justificante_numero.startswith("REC-MAD-"))

    def test_bd_impide_validar_quien_conto(self):
        self._cobro(40).action_post()
        cierre = self._cierre(40)
        cierre.action_contar()
        with self.assertRaises(psycopg2.errors.CheckViolation), mute_logger("odoo.sql_db"), self.cr.savepoint():
            self.cr.execute("UPDATE sp_cierre_caja SET validado_por = contado_por, estado = 'validado' WHERE id = %s",
                            [cierre.id])

    def test_bd_impide_cambiar_o_borrar_cierre_validado(self):
        self._cobro(40).action_post()
        cierre = self._cierre(40)
        cierre.action_contar()
        cierre.with_user(self.conta1).action_validar()
        with self.assertRaises(psycopg2.errors.RaiseException), mute_logger("odoo.sql_db"), self.cr.savepoint():
            self.cr.execute("UPDATE sp_cierre_caja SET contado = 1 WHERE id = %s", [cierre.id])
        with self.assertRaises(psycopg2.errors.RaiseException), mute_logger("odoo.sql_db"), self.cr.savepoint():
            self.cr.execute("DELETE FROM sp_cierre_caja WHERE id = %s", [cierre.id])

    def test_apunte_de_caja_de_dia_validado_no_vuelve_a_borrador(self):
        otro = self.env["account.payment"].create({
            "payment_type": "outbound", "partner_type": "supplier", "partner_id": self.cliente2.id, "amount": 10,
            "journal_id": self.caja.id})
        otro.action_post()
        cierre = self._cierre(-10, notas=False)
        cierre.action_contar()
        cierre.with_user(self.conta1).action_validar()
        with self.assertRaises(UserError):
            otro.move_id.button_draft()
        with self.assertRaises(UserError):
            otro.action_draft()

# Pruebas de sp_recepcion con DATOS FICTICIOS. Especificación: Sistema Propio F5.2 (tests/test_f52_recepcion.py).
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

from .common import SpRecepcionCommon


@tagged("post_install", "-at_install", "sp_recepcion")
class TestRecepcion(SpRecepcionCommon):

    # --- Cobros y justificante -----------------------------------------------------------------------------
    def test_cobro_con_justificante_numerado_por_sede(self):
        c1 = self._cobro(50)
        self.assertEqual(c1.sp_sede_id, self.sede, "La sede se toma de la sede habitual del usuario")
        c1.action_post()
        c2 = self._cobro(30, cliente=self.cliente2)
        c2.action_post()
        anio = c1.date.year
        self.assertEqual(c1.state, "paid")
        self.assertEqual(c1.sp_estado, "registrado")
        self.assertEqual(c1.sp_justificante_numero, f"REC-BCN-{anio}-000001")
        self.assertEqual(c2.sp_justificante_numero, f"REC-BCN-{anio}-000002")
        apunte = c1.move_id.line_ids.filtered(lambda l: l.account_id == self.caja.default_account_id)
        self.assertEqual(apunte.debit, 50.0, "El efectivo entra directamente en la cuenta de la caja")

    def test_tipo_obligatorio(self):
        with self.assertRaises(UserError):
            self._cobro(sp_tipo=False).action_post()

    def test_cobro_repetido_exige_motivo_y_avisa_a_contabilidad(self):
        self._cobro(50).action_post()
        repetido = self._cobro(50)
        with self.assertRaises(UserError):
            repetido.action_post()
        repetido.sp_motivo_duplicado = "corto"
        with self.assertRaises(UserError):
            repetido.action_post()
        repetido.sp_motivo_duplicado = "Son dos consultas distintas del mismo cliente"
        repetido.action_post()
        self.assertEqual(repetido.state, "paid")
        self.assertTrue(repetido.activity_ids.filtered(lambda a: a.user_id in (self.conta1 | self.conta2)),
                        "Contabilidad recibe una actividad para revisar el posible repetido")

    def test_misma_referencia_es_posible_repetido(self):
        self._cobro(50, memo="TPV-778").action_post()
        with self.assertRaises(UserError):
            self._cobro(80, cliente=self.cliente2, memo="tpv-778").action_post()

    # --- Confirmar y anular --------------------------------------------------------------------------------
    def test_confirmar_solo_contabilidad(self):
        c = self._cobro()
        c.action_post()
        with self.assertRaises(AccessError):
            c.with_user(self.recepcion).action_sp_confirmar()
        c.with_user(self.conta1).action_sp_confirmar()
        self.assertEqual(c.sp_estado, "confirmado")
        self.assertEqual(c.sp_confirmado_por, self.conta1)

    def test_anular_con_motivo_y_sin_volver_a_borrador(self):
        c = self._cobro()
        c.action_post()
        numero = c.sp_justificante_numero
        with self.assertRaises(UserError):
            c.action_draft()
        with self.assertRaises(UserError):
            c.action_cancel()
        with self.assertRaises(AccessError):
            c.with_user(self.recepcion)._sp_anular("Cobro registrado por error")
        with self.assertRaises(UserError):
            c.with_user(self.conta1)._sp_anular("corto")
        c.with_user(self.conta1)._sp_anular("Cobro registrado por error en la sede")
        self.assertEqual(c.state, "canceled")
        self.assertEqual(c.sp_estado, "anulado")
        self.assertEqual(c.sp_justificante_numero, numero, "El número del justificante se conserva")
        with self.assertRaises(UserError):
            c.unlink()

    # --- Cierre de caja ------------------------------------------------------------------------------------
    def test_cierre_sin_diferencia_validado_por_otra_persona(self):
        self._cobro(50).action_post()
        self._cobro(30, cliente=self.cliente2).action_post()
        cierre = self._cierre(80)
        cierre.action_contar()
        self.assertEqual((cierre.estado, cierre.esperado, cierre.diferencia), ("pendiente", 80.0, 0.0))
        with self.assertRaises(AccessError):
            cierre.with_user(self.recepcion).action_validar()
        cierre.with_user(self.conta1).action_validar()
        self.assertEqual(cierre.estado, "validado")
        self.assertFalse(cierre.ajuste_move_id)
        with self.assertRaises(UserError):
            cierre.contado = 90
        with self.assertRaises(UserError):
            cierre.unlink()

    def test_no_se_anula_un_cobro_de_un_dia_validado(self):
        c = self._cobro(50)
        c.action_post()
        cierre = self._cierre(50)
        cierre.action_contar()
        cierre.with_user(self.conta1).action_validar()
        with self.assertRaises(UserError):
            c.with_user(self.conta1)._sp_anular("Me he equivocado de importe")

    def test_cierre_con_diferencia_exige_motivo_y_crea_ajuste(self):
        self._cobro(80).action_post()
        cierre = self._cierre(75)
        with self.assertRaises(UserError):
            cierre.action_contar()
        cierre.notas = "Faltan 5 euros de cambio"
        cierre.action_contar()
        self.assertEqual(cierre.diferencia, -5.0)
        cierre.with_user(self.conta2).action_validar()
        self.assertTrue(cierre.ajuste_move_id, "La diferencia se contabiliza al validar")
        self.assertEqual(cierre.ajuste_move_id.state, "posted")
        self.assertEqual(cierre._saldo_registros(), 75.0, "Tras el ajuste, la caja cuadra con lo contado")

    def test_quien_cuenta_no_valida(self):
        self._cobro(40).action_post()
        cierre = self._cierre(40, usuario=self.conta1)
        cierre.with_user(self.conta1).action_contar()
        with self.assertRaises(UserError):
            cierre.with_user(self.conta1).action_validar()
        cierre.with_user(self.conta2).action_validar()
        self.assertEqual(cierre.estado, "validado")

    def test_un_cierre_por_dia_salvo_rechazado(self):
        self._cobro(40).action_post()
        primero = self._cierre(40)
        primero.action_contar()
        with self.assertRaises(ValidationError):
            self._cierre(40)
        with self.assertRaises(UserError):
            primero.with_user(self.conta1).action_rechazar()
        primero.with_user(self.conta1).nota_validacion = "Recuento hecho antes de cerrar la caja"
        primero.with_user(self.conta1).action_rechazar()
        self.assertEqual(primero.estado, "rechazado")
        segundo = self._cierre(40)
        segundo.action_contar()
        self.assertEqual(segundo.estado, "pendiente")

    def test_movimientos_tras_recuento_impiden_validar(self):
        self._cobro(40).action_post()
        cierre = self._cierre(40)
        cierre.action_contar()
        self._cobro(10, cliente=self.cliente2).action_post()
        with self.assertRaises(UserError):
            cierre.with_user(self.conta1).action_validar()

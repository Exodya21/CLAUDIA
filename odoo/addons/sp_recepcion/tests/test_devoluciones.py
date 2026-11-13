# Devoluciones a clientes con DATOS FICTICIOS. Especificación: Sistema Propio F5.0 (REFUND_FLOW) y charter 3.9/4.4.
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import SpRecepcionCommon


@tagged("post_install", "-at_install", "sp_recepcion")
class TestDevoluciones(SpRecepcionCommon):

    def _solicitar(self, importe=50.0, usuario=None, **extra):
        vals = {"partner_id": self.cliente.id, "importe": importe,
                "motivo": "El cliente canceló la cita con antelación suficiente"}
        vals.update(extra)
        return self.env["sp.devolucion"].with_user(usuario or self.recepcion).create(vals)

    def test_motivo_obligatorio_y_numeracion(self):
        with self.assertRaises(UserError):
            self._solicitar(motivo="corto")
        d = self._solicitar()
        self.assertTrue(d.name.startswith("DEV/"))
        self.assertEqual((d.estado, d.solicitado_por), ("registrada", self.recepcion))
        self.assertTrue(d.sudo().activity_ids.filtered(lambda a: a.user_id == self.atc),
                        "Atención al cliente recibe la tarea de revisarla")
        self.assertFalse(d.sudo().activity_ids.filtered(lambda a: a.user_id in (self.conta1 | self.conta2)),
                         "Si hay Atención al cliente, la revisión no se asigna a Contabilidad")

    def test_flujo_completo_con_letrado_y_pago_en_caja(self):
        self._cobro(50).action_post()
        d = self._solicitar(sede_id=self.sede.id)
        with self.assertRaises(AccessError):
            d.with_user(self.recepcion).action_revisar()
        d.with_user(self.atc).action_revisar()
        with self.assertRaises(UserError):
            d.with_user(self.atc).action_escalar()
        d.with_user(self.atc).informe_revision = "La cita no se llegó a celebrar; hay dudas sobre el encargo"
        d.with_user(self.atc).action_escalar()
        self.assertEqual(d.estado, "escalada_legal")
        with self.assertRaises(AccessError):
            d.with_user(self.atc).action_informe_letrado()
        d.with_user(self.letrado).opinion_legal = "Procede la devolución íntegra según la hoja de encargo"
        d.with_user(self.letrado).action_informe_letrado()
        self.assertEqual((d.estado, d.opinion_legal_por), ("en_revision", self.letrado))
        with self.assertRaises(AccessError):
            d.with_user(self.atc).action_aprobar()
        d.with_user(self.conta1).action_aprobar()
        self.assertEqual((d.estado, d.decidido_por), ("aprobada", self.conta1))
        with self.assertRaises(UserError):
            d.with_user(self.conta1).action_pagar()
        d.with_user(self.conta1).diario_pago_id = self.caja
        d.with_user(self.conta1).action_pagar()
        self.assertEqual(d.estado, "pagada")
        self.assertFalse(d.sudo().activity_ids, "Al terminar no quedan tareas pendientes")
        self.assertEqual((d.pago_id.payment_type, d.pago_id.amount, d.pago_id.state), ("outbound", 50.0, "paid"))
        cierre = self._cierre(0)
        cierre.action_contar()
        self.assertEqual(cierre.esperado, 0.0, "Cobro de 50 € menos devolución de 50 €: la caja queda a cero")

    def test_quien_solicita_no_decide(self):
        d = self._solicitar(usuario=self.conta1)
        with self.assertRaises(UserError):
            d.with_user(self.conta1).action_aprobar()
        d.with_user(self.conta2).action_aprobar()
        self.assertEqual(d.estado, "aprobada")

    def test_rechazar_y_reabrir_con_motivo(self):
        d = self._solicitar()
        with self.assertRaises(UserError):
            d.with_user(self.conta1).action_rechazar()
        d.with_user(self.conta1).motivo_decision = "La consulta se prestó: no procede devolver"
        d.with_user(self.conta1).action_rechazar()
        self.assertEqual(d.estado, "rechazada")
        d.with_user(self.conta1).motivo_decision = "corto"
        with self.assertRaises(UserError):
            d.with_user(self.conta1).action_reabrir()
        d.with_user(self.conta1).motivo_decision = "El cliente aporta prueba de que avisó a tiempo"
        d.with_user(self.conta1).action_reabrir()
        self.assertEqual(d.estado, "en_revision")

    def test_estado_solo_con_botones_y_no_se_borra(self):
        d = self._solicitar()
        with self.assertRaises(UserError):
            d.with_user(self.conta1).write({"estado": "pagada"})
        with self.assertRaises((UserError, AccessError)):
            d.with_user(self.conta1).unlink()

    def test_recepcion_solo_ve_sus_solicitudes(self):
        d = self._solicitar()
        D = self.env["sp.devolucion"]
        self.assertEqual(D.with_user(self.recepcion).search([]), d)
        self.assertFalse(D.with_user(self.recepcion_mad).search([]))
        self.assertFalse(D.with_user(self.letrado).search([]), "El letrado solo ve las escaladas")
        self.assertEqual(D.with_user(self.atc).search([]), d)

    def _factura(self, importe):
        factura = self.env["account.move"].create({
            "move_type": "out_invoice", "partner_id": self.cliente.id,
            "invoice_line_ids": [(0, 0, {"name": "Consulta inicial", "quantity": 1, "price_unit": importe,
                                         "tax_ids": [(5, 0, 0)]})]})
        factura.action_post()
        return factura

    def _cobrar(self, factura):
        self.env["account.payment.register"].with_context(active_model="account.move", active_ids=factura.ids).create(
            {"journal_id": self.caja.id})._create_payments()

    def test_devolucion_total_de_factura_crea_rectificativa(self):
        factura = self._factura(40.0)
        sin_cobrar = self._solicitar(40.0, factura_id=factura.id)
        sin_cobrar.with_user(self.conta1).action_aprobar()
        sin_cobrar.with_user(self.conta1).write({"diario_pago_id": self.caja.id})
        with self.assertRaises(UserError):
            sin_cobrar.with_user(self.conta1).action_pagar()
        self._cobrar(factura)
        d = self._solicitar(40.0, factura_id=factura.id)
        d.with_user(self.conta1).action_aprobar()
        d.with_user(self.conta1).write({"diario_pago_id": self.caja.id})
        d.with_user(self.conta1).action_pagar()
        self.assertEqual(d.rectificativa_id.move_type, "out_refund")
        self.assertEqual(d.rectificativa_id.state, "posted")
        self.assertIn(d.rectificativa_id.payment_state, ("paid", "in_payment"))

    def test_devolucion_parcial_exige_rectificativa_vinculada(self):
        factura = self._factura(100.0)
        self._cobrar(factura)
        d = self._solicitar(40.0, factura_id=factura.id)
        d.with_user(self.conta1).action_aprobar()
        d.with_user(self.conta1).write({"diario_pago_id": self.caja.id})
        with self.assertRaises(UserError):
            d.with_user(self.conta1).action_pagar()

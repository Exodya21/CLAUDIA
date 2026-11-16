# Facturación y conciliación por expediente con DATOS FICTICIOS.
from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import new_test_user, tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install", "sp_facturacion")
class TestFacturacionExpediente(AccountTestInvoicingCommon):

    @classmethod
    @AccountTestInvoicingCommon.setup_country("es")
    def setUpClass(cls):
        super().setUpClass()
        cls.banco = cls.company_data["default_journal_bank"]
        cls.conta = new_test_user(cls.env, "test.sp.fact.conta", groups="sp_recepcion.group_sp_responsable",
                                  company_id=cls.env.company.id, company_ids=[(6, 0, cls.env.company.ids)])
        cls.otro = new_test_user(cls.env, "test.sp.fact.otro", groups="account.group_account_invoice",
                                 company_id=cls.env.company.id, company_ids=[(6, 0, cls.env.company.ids)])
        cls.empresa = cls.env["res.partner"].create({"name": "EMPRESA_01 S.L.", "vat": "ESB87654323"})
        cls.particular = cls.env["res.partner"].create({"name": "CLIENTE_01"})

    def _expediente(self, cliente, honorarios, area="laboral"):
        e = self.env["sp.expediente"].with_user(self.otro).create(
            {"area": area, "partner_id": cliente.id, "fecha_apertura": "2026-11-02"})
        e.sp_honorarios = honorarios
        e.action_sp_fijar_honorarios()
        return e

    def _pago(self, importe, texto, fecha="2026-11-10"):
        st = self.env["account.bank.statement.line"].create(
            {"journal_id": self.banco.id, "date": fecha, "amount": importe, "payment_ref": texto})
        st._sp_proponer()
        return st

    def test_moneda_de_la_compania_aunque_la_tarifa_sea_otra(self):
        otra = self.env["res.currency"].search([("id", "!=", self.env.company.currency_id.id)], limit=1)
        otra.active = True
        tarifa = self.env["product.pricelist"].create({"name": "Tarifa en otra moneda", "currency_id": otra.id})
        self.particular.property_product_pricelist = tarifa
        e = self._expediente(self.particular, 100.0)
        self.assertEqual(e.sale_order_id.currency_id, self.env.company.currency_id)

    def test_honorarios_con_y_sin_retencion(self):
        e = self._expediente(self.empresa, 1000.0)
        self.assertTrue(e.sp_retencion)
        self.assertAlmostEqual(e.sp_total_pactado, 1060.0)  # 1000 + 210 IVA − 150 IRPF
        p = self._expediente(self.particular, 1000.0, "extranjeria")
        self.assertFalse(p.sp_retencion)
        self.assertAlmostEqual(p.sp_total_pactado, 1210.0)
        self.assertEqual(p.sp_estado_cobro, "pendiente")

    def test_anticipos_y_factura_final(self):
        e = self._expediente(self.empresa, 1000.0)
        # Primer pago: concepto troceado por la Norma 43
        st1 = self._pago(318.0, f"TRANSFERENCIA EMPRESA_01 PAGO {e.name[:6]} {e.name[6:]}")
        self.assertEqual((st1.sp_estado, st1.sp_regla, st1.sp_expediente_id), ("propuesto", "expediente", e),
                         st1.sp_explicacion)
        self.assertIn("anticipo", st1.sp_explicacion)
        with self.assertRaises(AccessError):
            st1.with_user(self.otro).action_sp_validar()
        st1.with_user(self.conta).action_sp_validar()
        f1 = st1.sp_factura_expediente_id
        self.assertEqual(f1.state, "posted")
        self.assertEqual(f1.currency_id, self.env.company.currency_id)
        self.assertAlmostEqual(f1.amount_untaxed, 300.0)
        self.assertAlmostEqual(f1.amount_total, 318.0)
        self.assertEqual(f1.payment_state, "paid")
        self.assertEqual(f1.invoice_date, fields.Date.today())  # fecha de emisión: la serie va en orden de fechas
        self.assertEqual(str(f1.delivery_date), "2026-11-10")  # fecha del pago = fecha de operación
        self.assertTrue(st1.is_reconciled)
        self.assertAlmostEqual(e.sp_pendiente, 742.0)
        self.assertEqual(e.sp_estado_cobro, "en_curso")
        # Pago de más: excepción
        st_mal = self._pago(800.0, f"PAGO {e.name}")
        self.assertEqual((st_mal.sp_estado, st_mal.sp_regla), ("excepcion", "expediente_pago_excesivo"))
        # Último pago: anticipo + factura final a 0 €
        st2 = self._pago(742.0, f"PAGO FINAL {e.name}", fecha="2026-11-20")
        self.assertIn("factura final", st2.sp_explicacion)
        st2.with_user(self.conta).action_sp_validar()
        self.assertEqual(e.sp_estado_cobro, "pagado")
        finales = e.sp_factura_ids.filtered(lambda m: m.currency_id.is_zero(m.amount_total))
        self.assertEqual(len(finales), 1)
        final = finales
        self.assertEqual(final.state, "posted")
        self.assertAlmostEqual(final.amount_untaxed, 0.0)
        self.assertTrue(any(l.price_subtotal == 1000.0 for l in final.invoice_line_ids))
        self.assertAlmostEqual(sum(l.price_subtotal for l in final.invoice_line_ids if l.price_subtotal < 0), -1000.0)
        self.assertEqual(len(e.sp_factura_ids), 3)

    def test_pago_unico_factura_normal(self):
        e = self._expediente(self.particular, 500.0, "extranjeria")
        st = self._pago(605.0, f"{e.name} CLIENTE_01")
        self.assertIn("UNA factura", st.sp_explicacion)
        st.with_user(self.conta).action_sp_validar()
        self.assertEqual(len(e.sp_factura_ids), 1)
        self.assertAlmostEqual(e.sp_factura_ids.amount_total, 605.0)
        self.assertEqual(e.sp_estado_cobro, "pagado")

    def test_importes_con_centimos(self):
        e = self._expediente(self.empresa, 1234.56)
        st = self._pago(123.45, f"PAGO {e.name}")
        st.with_user(self.conta).action_sp_validar()
        self.assertAlmostEqual(st.sp_factura_expediente_id.amount_total, 123.45)
        self.assertTrue(st.is_reconciled)

    def test_excepciones(self):
        st = self._pago(100.0, "PAGO LAB-2026-9999")
        self.assertEqual((st.sp_estado, st.sp_regla), ("excepcion", "expediente_no_existe"))
        e = self.env["sp.expediente"].create({"area": "laboral", "partner_id": self.particular.id})
        st = self._pago(100.0, f"PAGO {e.name}")
        self.assertEqual((st.sp_estado, st.sp_regla, st.sp_expediente_id), ("excepcion", "expediente_sin_honorarios", e))
        e.sp_honorarios = 100.0
        e.action_sp_fijar_honorarios()
        with self.assertRaises(UserError):
            e.action_sp_fijar_honorarios()
        st._sp_proponer()
        self.assertEqual(st.sp_regla, "expediente")

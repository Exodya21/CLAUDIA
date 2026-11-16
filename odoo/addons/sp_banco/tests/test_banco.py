# Banco y conciliación con DATOS FICTICIOS. Especificación: Sistema Propio F5.1 (tests/test_f51_agentes_banco.py)
# y F5.5 (test_f55_extractos_excel.py).
from datetime import date

from odoo.exceptions import AccessError, UserError
from odoo.tests import new_test_user, tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon

from ..lectura import extractos


@tagged("post_install", "-at_install", "sp_banco")
class TestBanco(AccountTestInvoicingCommon):

    @classmethod
    @AccountTestInvoicingCommon.setup_country("es")
    def setUpClass(cls):
        super().setUpClass()
        cls.banco_a = cls.company_data["default_journal_bank"]
        cuenta = cls.env["res.partner.bank"].create({"account_number": "ES0021000001110000012345",
                                                     "partner_id": cls.env.company.partner_id.id})
        cls.banco_a.bank_account_id = cuenta
        cls.banco_b = cls.banco_a.copy({"name": "Banco B (test)", "code": "TBB", "bank_account_id": False})
        cls.conta = new_test_user(cls.env, "test.sp.banco.conta",
                                  groups="sp_recepcion.group_sp_responsable",
                                  company_id=cls.env.company.id, company_ids=[(6, 0, cls.env.company.ids)])
        cls.otro = new_test_user(cls.env, "test.sp.banco.otro", groups="account.group_account_invoice",
                                 company_id=cls.env.company.id, company_ids=[(6, 0, cls.env.company.ids)])
        cls.cliente = cls.env["res.partner"].create({"name": "CLIENTE_01"})
        cls.Line = cls.env["account.bank.statement.line"]

    def _mov(self, importe, texto, banco=None, fecha="2026-11-05", **extra):
        return self.Line.create({"journal_id": (banco or self.banco_a).id, "date": fecha, "amount": importe,
                                 "payment_ref": texto, **extra})

    def _factura(self, importe):
        f = self.env["account.move"].create({
            "move_type": "out_invoice", "partner_id": self.cliente.id, "invoice_date": "2026-11-01",
            "invoice_line_ids": [(0, 0, {"name": "Honorarios", "quantity": 1, "price_unit": importe, "tax_ids": [(5, 0, 0)]})]})
        f.action_post()
        return f

    def _cobro_banco(self, factura=None, importe=None, fecha="2026-11-04"):
        if factura:
            return self.env["account.payment.register"].with_context(active_model="account.move", active_ids=factura.ids).create(
                {"journal_id": self.banco_a.id, "payment_date": fecha})._create_payments()
        p = self.env["account.payment"].create({"payment_type": "inbound", "partner_type": "customer",
                                                "partner_id": self.cliente.id, "amount": importe,
                                                "journal_id": self.banco_a.id, "date": fecha})
        p.action_post()
        return p

    # --- Importación ---------------------------------------------------------------------------------------
    def _n43(self, moves):
        return extractos.build_n43(bank="2100", branch="0001", account10="0000012345", start=date(2026, 11, 1),
                                   end=date(2026, 11, 5), opening_cents=100000, moves=moves)

    def test_importar_norma43_sin_duplicar_y_cuadre(self):
        datos = self._n43([(date(2026, 11, 3), 5000, "02", "REF1", "TRANSFERENCIA CLIENTE_01"),
                           (date(2026, 11, 4), -1250, "17", "REF2", "COMISION MANTENIMIENTO")])
        Imp = self.env["sp.banco.importacion"].with_user(self.conta)
        prueba = Imp._sp_importar("extracto.n43", datos, solo_comprobar=True)
        self.assertEqual((prueba.total, prueba.nuevos, prueba.cuadra), (2, 2, "si"))
        self.assertFalse(self.Line.search([("journal_id", "=", self.banco_a.id)]), "Comprobar no guarda nada")
        imp = Imp._sp_importar("extracto.n43", datos)
        self.assertEqual(imp.journal_id, self.banco_a, "Va a la cuenta cuyo IBAN termina igual (2345)")
        self.assertEqual(len(imp.statement_id.line_ids), 2)
        otra = Imp._sp_importar("extracto.n43", datos)
        self.assertEqual((otra.nuevos, otra.duplicados), (0, 2), "Reimportar no duplica")

    def test_no_adivina_la_cuenta(self):
        datos = extractos.build_n43(bank="2100", branch="0001", account10="0000099999", start=date(2026, 11, 1),
                                    end=date(2026, 11, 5), opening_cents=0, moves=[(date(2026, 11, 3), 100, "02", "R", "X")])
        with self.assertRaises(UserError):
            self.env["sp.banco.importacion"]._sp_importar("otra.n43", datos)

    # --- Propuestas y validación ---------------------------------------------------------------------------
    def test_referencia_de_factura_con_cobro_registrado(self):
        f = self._factura(300.0)
        self._cobro_banco(f)
        st = self._mov(300.0, f"TRANSFERENCIA {f.name} CLIENTE_01")
        st._sp_proponer()
        self.assertEqual((st.sp_estado, st.sp_regla), ("propuesto", "referencia"), st.sp_explicacion)
        with self.assertRaises(AccessError):
            st.with_user(self.otro).action_sp_validar()
        st.with_user(self.conta).action_sp_validar()
        self.assertTrue(st.is_reconciled)
        self.assertEqual(st.sp_estado, "conciliado")
        self.assertEqual(f.payment_state, "paid")

    def test_referencia_de_factura_sin_cobro(self):
        f = self._factura(120.0)
        st = self._mov(120.0, f"PAGO FACTURA {f.name}")
        st._sp_proponer()
        self.assertEqual(st.sp_regla, "referencia")
        st.with_user(self.conta).action_sp_validar()
        self.assertEqual(f.payment_state, "paid", "Sin cobro registrado, se concilia con la propia factura")

    def test_importe_y_fecha_y_rechazo_con_motivo(self):
        p = self._cobro_banco(importe=75.0)
        st = self._mov(75.0, "TRANSFERENCIA RECIBIDA")
        st._sp_proponer()
        self.assertEqual(st.sp_regla, "importe_fecha")
        with self.assertRaises(UserError):
            st.with_user(self.conta).action_sp_rechazar()
        st.with_user(self.conta).sp_nota = "No es ese cliente: el ordenante es otro"
        st.with_user(self.conta).action_sp_rechazar()
        self.assertEqual(st.sp_estado, "excepcion", "Rechazada, no vuelve a proponer el mismo cobro")
        self.assertFalse(st.is_reconciled)
        self.assertTrue(p)

    def test_traspaso_no_es_ingreso(self):
        a = self._mov(1000.0, "TRASPASO DESDE CUENTA B")
        b = self._mov(-1000.0, "TRASPASO A CUENTA A", banco=self.banco_b)
        a._sp_proponer()
        self.assertEqual((a.sp_regla, a.sp_contrapartida_id), ("traspaso", b))
        a.with_user(self.conta).action_sp_validar()
        self.assertEqual((a.sp_estado, b.sp_estado), ("traspaso", "traspaso"))
        self.assertTrue(a.is_reconciled and b.is_reconciled)
        self.assertFalse(a.move_id.line_ids.filtered(lambda l: l.account_id.account_type == "income"))

    def test_ingreso_sin_identificar_y_contabilizar_en_cuenta(self):
        ingreso = self._mov(42.0, "INGRESO EN EFECTIVO")
        ingreso._sp_proponer()
        self.assertEqual((ingreso.sp_estado, ingreso.sp_regla), ("excepcion", "ingreso_sin_identificar"))
        comision = self._mov(-2.5, "COMISION MANTENIMIENTO CUENTA")
        comision._sp_proponer()
        self.assertEqual((comision.sp_regla, comision.sp_categoria), ("cargo_sin_justificar", "Comisión bancaria"))
        comision.with_user(self.conta).sp_cuenta_id = self.company_data["default_account_expense"]
        with self.assertRaises(UserError):
            comision.with_user(self.conta).action_sp_contabilizar_en_cuenta()
        comision.with_user(self.conta).sp_nota = "Comisión de mantenimiento mensual"
        comision.with_user(self.conta).action_sp_contabilizar_en_cuenta()
        self.assertTrue(comision.is_reconciled)
        self.assertEqual(comision.sp_estado, "justificado")

    def test_devolucion_pagada_por_banco(self):
        d = self.env["sp.devolucion"].sudo().create({"partner_id": self.cliente.id, "importe": 50.0,
                                                     "motivo": "Cita cancelada con antelación suficiente"})
        d.with_user(self.conta).action_aprobar()
        d.with_user(self.conta).diario_pago_id = self.banco_a
        d.with_user(self.conta).action_pagar()
        st = self._mov(-50.0, "TRANSFERENCIA EMITIDA CLIENTE_01", fecha=str(d.pago_id.date))
        st._sp_proponer()
        self.assertEqual(st.sp_regla, "devolucion", st.sp_explicacion)
        st.with_user(self.conta).action_sp_validar()
        self.assertTrue(st.is_reconciled)

    def test_referencia_partida_por_la_norma43(self):
        f = self._factura(90.0)
        partida = f.name[:-1] + " " + f.name[-1]
        st = self._mov(90.0, f"TRANSFERENCIA CLIENTE_01 {partida}")
        st._sp_proponer()
        self.assertEqual(st.sp_regla, "referencia", st.sp_explicacion)

    def test_traspaso_importado_en_dos_veces(self):
        c = self._mov(500.0, "TRASPASO DESDE BANCO B", banco=self.banco_b)
        c._sp_proponer()
        self.assertEqual(c.sp_estado, "excepcion", "Aún no está el otro extracto")
        b = self._mov(-500.0, "TRASPASO A BANCO B")
        b._sp_proponer()
        self.assertEqual((b.sp_regla, b.sp_contrapartida_id), ("traspaso", c))
        c._sp_proponer()
        self.assertEqual((c.sp_regla, c.sp_contrapartida_id), ("traspaso", b))
        c.with_user(self.conta).action_sp_validar()
        self.assertEqual((b.sp_estado, c.sp_estado), ("traspaso", "traspaso"))

    # --- Remates: TPV con comisión, elegir a mano, pago parcial, exportación ----------------------------------
    def test_tpv_con_comision_va_a_la_626(self):
        self._cobro_banco(importe=60.0, fecha="2026-11-03")
        self._cobro_banco(importe=40.0, fecha="2026-11-03")
        st = self._mov(98.5, "LIQUIDACION TPV COMERCIO 03/11")
        st._sp_proponer()
        self.assertEqual((st.sp_estado, st.sp_regla), ("propuesto", "tpv_comision"), st.sp_explicacion)
        self.assertAlmostEqual(st.sp_ajuste_importe, -1.5)
        self.assertEqual(st.sp_ajuste_cuenta_id.code[:3], "626")
        st.with_user(self.conta).action_sp_validar()
        self.assertTrue(st.is_reconciled)
        comision = st.move_id.line_ids.filtered(lambda l: l.account_id == st.sp_ajuste_cuenta_id)
        self.assertAlmostEqual(comision.debit, 1.5)

    def test_tpv_comision_excesiva_no_se_propone(self):
        self._cobro_banco(importe=100.0, fecha="2026-11-03")
        st = self._mov(90.0, "LIQUIDACION TPV")
        st._sp_proponer()
        self.assertEqual((st.sp_estado, st.sp_regla), ("excepcion", "tpv_sin_cuadre"))

    def test_elegir_a_mano_y_pago_parcial(self):
        f = self._factura(300.0)
        st = self._mov(100.0, "INGRESO SIN REFERENCIA")
        st._sp_proponer()
        self.assertEqual(st.sp_estado, "excepcion")
        receivable = f.line_ids.filtered(lambda l: l.account_id.account_type == "asset_receivable")
        st.sp_manual_aml_ids = receivable
        with self.assertRaises(AccessError):
            st.with_user(self.otro).action_sp_elegir_a_mano()
        st.with_user(self.conta).action_sp_elegir_a_mano()
        self.assertEqual(st.sp_regla, "manual_parcial")
        st.with_user(self.conta).action_sp_validar()
        self.assertTrue(st.is_reconciled)
        self.assertEqual(f.payment_state, "partial")
        self.assertAlmostEqual(f.amount_residual, 200.0)

    def test_elegir_a_mano_con_diferencia_exige_cuenta_y_motivo(self):
        f = self._factura(100.0)
        st = self._mov(102.0, "TRANSFERENCIA CON 2 EUROS DE MAS")
        st.sp_manual_aml_ids = f.line_ids.filtered(lambda l: l.account_id.account_type == "asset_receivable")
        with self.assertRaises(UserError):
            st.with_user(self.conta).action_sp_elegir_a_mano()
        cuenta = self.env["account.account"].search([("code", "=like", "778%")], limit=1) or \
            self.company_data["default_account_revenue"]
        st.write({"sp_cuenta_id": cuenta.id, "sp_nota": "El cliente pagó 2 euros de más; se le avisa."})
        st.with_user(self.conta).action_sp_elegir_a_mano()
        self.assertEqual(st.sp_regla, "manual_diferencia")
        st.with_user(self.conta).action_sp_validar()
        self.assertEqual(f.payment_state, "paid")
        self.assertAlmostEqual(st.move_id.line_ids.filtered(lambda l: l.account_id == cuenta).credit, 2.0)

    def test_exportar_csv_gestoria(self):
        self._cobro_banco(importe=55.0)
        st = self._mov(55.0, "BIZUM CLIENTE_01")
        st._sp_proponer()
        st.with_user(self.conta).action_sp_validar()
        w = self.env["sp.banco.exportar"].with_user(self.conta).create(
            {"fecha_desde": "2026-11-01", "fecha_hasta": "2026-11-30"})
        accion = w.action_exportar()
        adjunto = self.env["ir.attachment"].browse(int(accion["url"].split("/")[3].split("?")[0]))
        texto = adjunto.raw.content.decode("utf-8-sig") if hasattr(adjunto.raw, "content") else adjunto.raw.decode("utf-8-sig")
        self.assertIn("Fecha;Fecha valor;Cuenta;Concepto", texto)
        self.assertIn("BIZUM CLIENTE_01", texto)
        self.assertIn("55,00", texto)
        self.assertNotIn("ES0021", texto)
        with self.assertRaises(UserError):
            self.env["sp.banco.exportar"].with_user(self.otro).create(
                {"fecha_desde": "2026-11-01", "fecha_hasta": "2026-11-30"}).action_exportar()

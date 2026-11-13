# Gastos de empleados con DATOS FICTICIOS. Especificación: Sistema Propio F5.0 (tests/test_f50_gastos.py).
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.sp_contabilidad.lectura import extraer
from odoo.addons.sp_contabilidad.tests.test_facturas_proveedor import factura_pdf

TICKET = [
    "BAR EL RINCON FICTICIO SL",
    "CIF B87654323",
    "FACTURA SIMPLIFICADA 0001234",
    "Fecha 10/11/2026 14:32",
    "2 MENU DEL DIA 20,66",
    "BASE IMPONIBLE 20,66",
    "IVA 10% 2,07",
    "TOTAL 22,73 EUR",
]


@tagged("post_install", "-at_install", "sp_gastos")
class TestGastos(AccountTestInvoicingCommon):

    @classmethod
    @AccountTestInvoicingCommon.setup_country("es")
    def setUpClass(cls):
        super().setUpClass()
        cls.caja = cls.company_data["default_journal_cash"]
        for linea in cls.caja.inbound_payment_method_line_ids | cls.caja.outbound_payment_method_line_ids:
            linea.payment_account_id = cls.caja.default_account_id
        cls.sede = cls.env["sp.sede"].create({"name": "Barcelona", "code": "BCN", "journal_id": cls.caja.id})
        cls.usuario = cls.env["res.users"].sudo().create({
            "name": "EMPLEADO_01", "login": "test.sp.empleado", "sp_sede_id": cls.sede.id,
            "company_id": cls.env.company.id, "company_ids": [(6, 0, cls.env.company.ids)],
            "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])]})
        cls.empleado = cls.env["hr.employee"].sudo().create({"name": "EMPLEADO_01", "user_id": cls.usuario.id,
                                                      "company_id": cls.env.company.id})
        cls.producto = cls.env["product.product"].create({
            "name": "Dietas (test)", "type": "service", "can_be_expensed": True,
            "property_account_expense_id": cls.company_data["default_account_expense"].id,
            "supplier_taxes_id": [(5, 0, 0)]})

    def _gasto(self, importe=22.73, **vals):
        return self.env["hr.expense"].create({"name": "Comida con cliente", "employee_id": self.empleado.id,
                                              "product_id": self.producto.id, "total_amount_currency": importe,
                                              **vals})

    def test_sede_de_la_persona(self):
        self.assertEqual(self._gasto().sp_sede_id, self.sede)

    def test_pagado_por_la_persona(self):
        g = self._gasto()
        self.assertEqual((g.sp_forma_pago, g.payment_mode), ("propio", "own_account"))

    def test_efectivo_sale_de_la_caja_de_la_sede(self):
        g = self._gasto(sp_forma_pago="efectivo")
        self.assertEqual(g.payment_mode, "company_account")
        self.assertEqual(g.payment_method_line_id.journal_id, self.caja)
        g.sudo().action_submit()
        g.sudo().action_approve()
        move = g.account_move_id
        self.assertTrue(move, "Al aprobar se crea el asiento")
        move.action_post()
        apunte_caja = move.line_ids.filtered(lambda l: l.account_id == self.caja.default_account_id)
        self.assertEqual(apunte_caja.credit, 22.73, "El efectivo sale de la cuenta de la caja de la sede")

    def test_efectivo_sin_sede_no_se_permite(self):
        self.usuario.sp_sede_id = False
        self.usuario.sp_sede_ids = [(5, 0, 0)]
        g = self._gasto()
        g.sp_sede_id = False
        with self.assertRaises(UserError):
            g.sp_forma_pago = "efectivo"

    def test_lectura_del_ticket(self):
        if not extraer.disponible():
            self.skipTest("Sin pdftotext/tesseract (usar la imagen de odoo/Dockerfile)")
        persona = self.env(user=self.usuario)  # la propia persona sube y lee su ticket
        g = persona["hr.expense"].create({"name": "Dietas (test)", "employee_id": self.empleado.id,
                                          "product_id": self.producto.id, "total_amount_currency": 0})
        persona["ir.attachment"].create({"name": "ticket.pdf", "raw": factura_pdf(TICKET), "mimetype": "application/pdf",
                                         "res_model": "hr.expense", "res_id": g.id})
        g.action_sp_leer_ticket()
        self.assertEqual(str(g.date), "2026-11-10")
        self.assertEqual(g.total_amount_currency, 22.73)
        self.assertEqual(g.vendor_id.vat, "ESB87654323")
        self.assertEqual(g.sp_iva_ticket, 2.07)
        self.assertEqual(g.tax_ids.amount, 10.0, "IVA del 10 % reconocido a partir de la cifra del ticket")
        self.assertAlmostEqual(g.tax_amount, 2.07, places=2)

    def test_iva_leido_se_mantiene_al_elegir_categoria(self):
        if not extraer.disponible():
            self.skipTest("Sin pdftotext/tesseract")
        persona = self.env(user=self.usuario)
        g = persona["hr.expense"].create({"name": "Dietas (test)", "employee_id": self.empleado.id,
                                          "product_id": self.producto.id, "total_amount_currency": 0})
        persona["ir.attachment"].create({"name": "ticket.pdf", "raw": factura_pdf(TICKET), "mimetype": "application/pdf",
                                         "res_model": "hr.expense", "res_id": g.id})
        g.action_sp_leer_ticket()
        otro = self.producto.copy({"name": "Otra categoría (test)"})
        g.product_id = otro
        self.assertEqual(g.tax_ids.amount, 10.0)

# Facturas de proveedores con DATOS FICTICIOS. Especificación: Sistema Propio F5.4/F5.5
# (tests/test_f54_contabilidad.py, tests/test_f55_lectura_facturas.py).
import io

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon

from ..lectura import extraer


def factura_pdf(lineas):
    """PDF ficticio con texto (como el de un proveedor)."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    y = 800
    for linea in lineas:
        c.drawString(60, y, linea)
        y -= 18
    c.save()
    return buf.getvalue()


FACTURA = [
    "ASESORES FICTICIOS SL",
    "CIF: B87654323",
    "Calle Inventada 1, Madrid",
    "FACTURA N.º F-2026/0042",
    "Fecha de factura: 05/11/2026",
    "Vencimiento: 05/12/2026",
    "Cliente: DESPACHO DEMO SL   CIF: B12345674",
    "Concepto: Asesoría fiscal octubre",
    "Base imponible 100,00 EUR",
    "IVA 21% 21,00 EUR",
    "Retención IRPF 15% 15,00 EUR",
    "TOTAL FACTURA 106,00 EUR",
]


@tagged("post_install", "-at_install", "sp_contabilidad")
class TestFacturasProveedor(AccountTestInvoicingCommon):

    @classmethod
    @AccountTestInvoicingCommon.setup_country("es")
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.vat = "ESB12345674"  # CIF ficticio del despacho: la lectura lo descarta

    def _borrador(self, **vals):
        return self.env["account.move"].create({"move_type": "in_invoice", **vals})

    def _adjuntar(self, move, datos, nombre="factura.pdf"):
        return self.env["ir.attachment"].create({"name": nombre, "raw": datos,
                                                 "res_model": "account.move", "res_id": move.id,
                                                 "mimetype": "application/pdf"})

    def test_lectura_propone_y_cuadra(self):
        if not extraer.disponible():
            self.skipTest("Sin pdftotext/tesseract (usar la imagen de odoo/Dockerfile)")
        move = self._borrador()
        self._adjuntar(move, factura_pdf(FACTURA))
        move.action_sp_leer_factura()
        self.assertEqual(move.partner_id.vat, "ESB87654323", "Proveedor por su CIF (no el del despacho)")
        self.assertEqual(move.ref, "F-2026/0042")
        self.assertEqual(str(move.invoice_date), "2026-11-05")
        self.assertEqual(move.sp_total_documento, 106.0)
        self.assertEqual(len(move.invoice_line_ids), 1)
        self.assertEqual(move.invoice_line_ids.price_unit, 100.0)
        self.assertEqual(sorted(move.invoice_line_ids.tax_ids.mapped("amount")), [-15.0, 21.0],
                         "IVA 21 % y retención 15 % reconocidos a partir de las cifras de la factura")
        self.assertEqual(move.amount_total, 106.0)
        move.action_post()
        self.assertEqual(move.state, "posted")

    def test_no_registra_si_no_cuadra_o_sin_total(self):
        move = self._borrador(partner_id=self.partner_a.id, invoice_date="2026-11-05", invoice_line_ids=[
            (0, 0, {"name": "Servicio", "quantity": 1, "price_unit": 100.0, "tax_ids": [(5, 0, 0)]})])
        with self.assertRaises(UserError):
            move.action_post()
        move.sp_total_documento = 121.0
        with self.assertRaises(UserError):
            move.action_post()
        move.sp_total_documento = 100.0
        move.action_post()
        self.assertEqual(move.state, "posted")

    def test_factura_repetida_exige_motivo(self):
        def factura(ref):
            return self._borrador(partner_id=self.partner_a.id, ref=ref, invoice_date="2026-11-05",
                                  sp_total_documento=50.0, invoice_line_ids=[
                                      (0, 0, {"name": "Servicio", "quantity": 1, "price_unit": 50.0,
                                              "tax_ids": [(5, 0, 0)]})])
        factura("A-1").action_post()
        repetida = factura("a-1")
        with self.assertRaises(UserError):
            repetida.action_post()
        mismo_importe = factura("A-2")
        with self.assertRaises(UserError):
            mismo_importe.action_post()
        mismo_importe.sp_motivo_duplicado = "Dos servicios distintos facturados el mismo día"
        mismo_importe.action_post()
        self.assertEqual(mismo_importe.state, "posted")

    def test_mismo_archivo_es_posible_repetida(self):
        datos = factura_pdf(["Factura de prueba ficticia", "Total 50,00"])
        a = self._borrador(partner_id=self.partner_a.id, ref="X-1", invoice_date="2026-11-01", sp_total_documento=50.0,
                           invoice_line_ids=[(0, 0, {"name": "S", "quantity": 1, "price_unit": 50.0, "tax_ids": [(5, 0, 0)]})])
        self._adjuntar(a, datos)
        a.action_post()
        b = self._borrador(partner_id=self.partner_b.id, ref="Y-9", invoice_date="2026-11-02", sp_total_documento=70.0,
                           invoice_line_ids=[(0, 0, {"name": "S", "quantity": 1, "price_unit": 70.0, "tax_ids": [(5, 0, 0)]})])
        self._adjuntar(b, datos)
        with self.assertRaises(UserError):
            b.action_post()

    def test_no_inventa_si_no_lee(self):
        if not extraer.disponible():
            self.skipTest("Sin pdftotext/tesseract")
        move = self._borrador()
        self._adjuntar(move, factura_pdf(["Documento sin datos de factura", "Hola"]))
        move.action_sp_leer_factura()
        self.assertFalse(move.invoice_line_ids)
        self.assertFalse(move.sp_total_documento)
        self.assertEqual(move.sp_lectura_confianza, "baja")

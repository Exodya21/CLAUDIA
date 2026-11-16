# Expedientes con DATOS FICTICIOS.
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from ..models.expediente import numeros_en_texto


@tagged("post_install", "-at_install", "sp_expediente")
class TestExpediente(TransactionCase):

    def test_numero_por_area_y_anio_sin_cambios(self):
        cli = self.env["res.partner"].create({"name": "CLIENTE_01"})
        a = self.env["sp.expediente"].create({"area": "laboral", "partner_id": cli.id, "fecha_apertura": "2026-11-16"})
        b = self.env["sp.expediente"].create({"area": "laboral", "partner_id": cli.id, "fecha_apertura": "2026-11-16"})
        c = self.env["sp.expediente"].create({"area": "extranjeria", "partner_id": cli.id, "fecha_apertura": "2026-11-16"})
        self.assertRegex(a.name, r"^LAB-2026-\d{4}$")
        self.assertEqual(int(b.name[-4:]), int(a.name[-4:]) + 1)
        self.assertRegex(c.name, r"^EXT-2026-\d{4}$")
        with self.assertRaises(UserError):
            a.name = "LAB-2026-9999"
        with self.assertRaises(UserError):
            a.area = "extranjeria"
        with self.assertRaises(UserError):
            a.unlink()

    def test_numero_en_concepto_tolerante(self):
        self.assertEqual(numeros_en_texto("TRANSF CLIENTE_01 LAB-2026-0007 PAGO 2"), ["LAB-2026-0007"])
        self.assertEqual(numeros_en_texto("ext 2026 0012"), ["EXT-2026-0012"])
        self.assertEqual(numeros_en_texto("LAB2026/0003"), ["LAB-2026-0003"])
        self.assertEqual(numeros_en_texto("TEXTO 2026 0001 SIN EXPEDIENTE"), [])

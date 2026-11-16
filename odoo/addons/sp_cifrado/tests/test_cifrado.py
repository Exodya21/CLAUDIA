# Cifrado de IBAN con DATOS FICTICIOS (IBAN de ejemplo con formato válido, no reales).
import os
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from .. import cifrado

IBAN = "ES9121000418450200051332"  # IBAN de ejemplo de la documentación bancaria, ficticio


@tagged("post_install", "-at_install", "sp_cifrado")
class TestCifrado(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cliente = cls.env["res.partner"].create({"name": "CLIENTE_01"})

    def _en_bd(self, tabla, columna, rid):
        self.env.flush_all()
        self.env.cr.execute(f'SELECT "{columna}" FROM "{tabla}" WHERE id = %s', [rid])
        return self.env.cr.fetchone()[0]

    def test_iban_cifrado_en_la_base_y_claro_en_odoo(self):
        b = self.env["res.partner.bank"].create({"account_number": IBAN, "partner_id": self.cliente.id})
        self.env.invalidate_all()
        self.assertEqual(b.sanitized_account_number, IBAN)
        self.assertIn("1332", b.account_number)
        crudo = self._en_bd("res_partner_bank", "account_number", b.id)
        self.assertTrue(crudo.startswith(cifrado.MARCA))
        self.assertNotIn("1332", crudo)
        self.assertNotIn(IBAN, self._en_bd("res_partner_bank", "sanitized_account_number", b.id))

    def test_busquedas_y_duplicados(self):
        b = self.env["res.partner.bank"].create({"account_number": IBAN, "partner_id": self.cliente.id})
        Bank = self.env["res.partner.bank"]
        self.assertEqual(Bank.search([("account_number", "=", IBAN)]), b)
        self.assertEqual(Bank.search([("account_number", "=", "ES91 2100 0418 4502 0005 1332")]), b)
        self.assertEqual(Bank.search([("sanitized_account_number", "in", [IBAN, "ES00"])]), b)
        self.assertIn(b, Bank.search([("account_number", "ilike", "0005 1332")]))
        self.assertNotIn(b, Bank.search([("account_number", "ilike", "9999 9999")]))
        with self.assertRaises(Exception), self.env.cr.savepoint():
            Bank.create({"account_number": IBAN, "partner_id": self.cliente.id})

    def test_historial_enmascarado(self):
        b = self.env["res.partner.bank"].create({"account_number": IBAN, "partner_id": self.cliente.id})
        b.account_number = "ES7921000813610123456789"
        textos = " ".join(self.cliente.message_ids.mapped("body"))
        self.assertIn("ES91 **** 1332", textos)
        self.assertIn("ES79 **** 6789", textos)
        self.assertNotIn(IBAN, textos)
        self.env.flush_all()
        self.env.cr.execute("SELECT count(*) FROM mail_message WHERE body::text LIKE %s", [f"%{IBAN[-8:]}%"])
        self.assertEqual(self.env.cr.fetchone()[0], 0, "El IBAN completo no queda en ningún mensaje")

    def test_sin_clave_no_guarda_y_no_revela(self):
        b = self.env["res.partner.bank"].create({"account_number": IBAN, "partner_id": self.cliente.id})
        self.env.flush_all()
        sin = {k: v for k, v in os.environ.items() if k != "SP_CLAVE_CIFRADO"}
        with patch.dict(os.environ, sin, clear=True), patch.dict(cifrado.config.options, {"sp_clave_cifrado": False}):
            self.env.invalidate_all()
            self.assertEqual(b.account_number, cifrado.FALTA_CLAVE)
            with self.assertRaises(UserError):
                self.env["res.partner.bank"].create({"account_number": "ES7921000813610123456789",
                                                     "partner_id": self.cliente.id})
                self.env.flush_all()
        self.env.invalidate_all()
        self.assertIn("1332", b.account_number)

    def test_archivos(self):
        datos = b"extracto ficticio"
        c = cifrado.cifrar_archivo(datos)
        self.assertNotIn(datos, c)
        self.assertEqual(cifrado.descifrar_archivo(c), datos)
        self.assertEqual(cifrado.enmascarar("ES91 2100 0418 4502 0005 1332"), "ES91 **** 1332")

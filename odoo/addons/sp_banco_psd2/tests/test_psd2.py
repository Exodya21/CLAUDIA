# Conexión PSD2 con DATOS FICTICIOS y el agregador SIMULADO (no sale nada a la red).
import base64
import json
import os
import tempfile
from datetime import date, timedelta
from unittest.mock import patch

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import new_test_user, tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon

from ..proveedores import enablebanking as eb

IBAN_PROPIO = "ES9121000418450200051332"  # ficticio
IBAN_OTRO = "ES7921000813610123456789"    # ficticio
IBAN_CLIENTE = "ES6000491500051234567892"  # ficticio


class Resp:
    def __init__(self, estado, datos):
        self.status_code, self._d = estado, datos
        self.content = json.dumps(datos).encode()

    def json(self):
        return self._d


def tx(importe, ind, texto, fecha, estado="BOOK", ref=None, nombre=None, iban=None):
    parte = "debtor" if ind == "CRDT" else "creditor"
    t = {"entry_reference": ref, "transaction_amount": {"amount": importe, "currency": "EUR"},
         "credit_debit_indicator": ind, "status": estado, "booking_date": fecha, "value_date": fecha,
         "remittance_information": [texto]}
    if nombre:
        t[parte] = {"name": nombre}
    if iban:
        t[f"{parte}_account"] = {"iban": iban}
    return t


@tagged("post_install", "-at_install", "sp_banco_psd2")
class TestPsd2(AccountTestInvoicingCommon):

    @classmethod
    @AccountTestInvoicingCommon.setup_country("es")
    def setUpClass(cls):
        super().setUpClass()
        cls.banco = cls.company_data["default_journal_bank"]
        cls.banco.bank_account_id = cls.env["res.partner.bank"].create(
            {"account_number": IBAN_PROPIO, "partner_id": cls.env.company.partner_id.id})
        cls.conta = new_test_user(cls.env, "test.sp.psd2.conta", groups="sp_recepcion.group_sp_responsable",
                                  company_id=cls.env.company.id, company_ids=[(6, 0, cls.env.company.ids)])
        cls.otro = new_test_user(cls.env, "test.sp.psd2.otro", groups="account.group_account_invoice",
                                 company_id=cls.env.company.id, company_ids=[(6, 0, cls.env.company.ids)])
        cls.clave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.pem = tempfile.NamedTemporaryFile(suffix=".pem", delete=False)
        cls.pem.write(cls.clave.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                              serialization.NoEncryption()))
        cls.pem.close()

    @classmethod
    def tearDownClass(cls):
        os.unlink(cls.pem.name)
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.env_patch = patch.dict(os.environ, {"SP_EB_APP_ID": "app-ficticia", "SP_EB_CLAVE": self.pem.name})
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)
        self.llamadas = []
        self.respuestas = {}
        p = patch.object(eb, "_http", side_effect=self._falso)
        p.start()
        self.addCleanup(p.stop)

    def _falso(self, metodo, ruta, **kw):
        self.llamadas.append((metodo, ruta, kw))
        r = self.respuestas.get((metodo, ruta))
        if callable(r):
            r = r(kw)
        return r or Resp(404, {"error": "NOT_FOUND"})

    def _conectar(self):
        c = self.env["sp.banco.conexion"].with_user(self.conta).create({"name": "BANCO_FICTICIO"})
        self.respuestas[("POST", "/auth")] = Resp(200, {"url": "https://banco.example/autorizar?x=1"})
        accion = c.action_autorizar()
        self.assertEqual(accion["url"], "https://banco.example/autorizar?x=1")
        cuerpo = self.llamadas[-1][2]["json"]
        self.assertEqual((cuerpo["aspsp"], cuerpo["psu_type"]), ({"name": "BANCO_FICTICIO", "country": "ES"}, "business"))
        self.assertTrue(cuerpo["redirect_url"].endswith("/sp_banco_psd2/vuelta"))
        self.assertEqual(c.estado, "pendiente")
        estado = c.sudo().estado_token
        hasta = (fields.Datetime.now() + timedelta(days=170)).isoformat()
        self.respuestas[("POST", "/sessions")] = Resp(200, {"session_id": "ses-ficticia", "access": {"valid_until": hasta},
            "accounts": [{"uid": "u1", "account_id": {"iban": IBAN_PROPIO}, "name": "Cuenta empresa"},
                         {"uid": "u2", "account_id": {"iban": IBAN_OTRO}}]})
        self.env["sp.banco.conexion"].with_user(self.conta)._sp_vuelta(estado, "codigo-ficticio")
        return c, estado

    def test_token_firmado(self):
        partes = eb.token(ahora=1_800_000_000).split(".")
        dec = lambda s: base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))
        cab, cuerpo = json.loads(dec(partes[0])), json.loads(dec(partes[1]))
        self.assertEqual((cab["alg"], cab["kid"]), ("RS256", "app-ficticia"))
        self.assertEqual((cuerpo["iss"], cuerpo["aud"], cuerpo["exp"] - cuerpo["iat"]),
                         ("enablebanking.com", "api.enablebanking.com", 3600))
        self.clave.public_key().verify(dec(partes[2]), f"{partes[0]}.{partes[1]}".encode(), padding.PKCS1v15(),
                                       hashes.SHA256())

    def test_autorizar_y_cuentas_por_iban_exacto(self):
        c, estado = self._conectar()
        self.assertEqual(c.estado, "activa")
        self.assertEqual(c.cuenta_ids.filtered(lambda x: x.journal_id == self.banco).iban, IBAN_PROPIO)
        self.assertFalse(c.cuenta_ids.filtered(lambda x: x.iban == IBAN_OTRO).journal_id, "No se adivina el diario")
        self.env.flush_all()
        self.env.cr.execute("SELECT sesion_id FROM sp_banco_conexion WHERE id = %s", [c.id])
        self.assertNotIn("ses-ficticia", self.env.cr.fetchone()[0], "La sesión se guarda cifrada")
        with self.assertRaises(UserError):  # el «state» es de un solo uso
            self.env["sp.banco.conexion"].with_user(self.conta)._sp_vuelta(estado, "otro")

    def test_sincronizar_sin_duplicar_y_solo_contabilizados(self):
        c, _e = self._conectar()
        pagina1 = {"transactions": [
            tx("50.00", "CRDT", "TRANSFERENCIA CLIENTE_01", "2026-11-10", ref="R1", nombre="CLIENTE_01", iban=IBAN_CLIENTE),
            tx("12.10", "DBIT", "COMISION MANTENIMIENTO", "2026-11-11", ref="R2"),
            tx("99.00", "CRDT", "PENDIENTE", "2026-11-12", estado="PDNG", ref="R3")], "continuation_key": "k2"}
        pagina2 = {"transactions": [tx("20.00", "CRDT", "BIZUM CLIENTE_02", "2026-11-12", ref="R4")]}
        self.respuestas[("GET", "/accounts/u1/transactions")] = \
            lambda kw: Resp(200, pagina2 if kw["params"].get("continuation_key") == "k2" else pagina1)
        c.with_user(self.conta).action_sincronizar()
        lineas = self.env["account.bank.statement.line"].search([("journal_id", "=", self.banco.id)])
        self.assertEqual(sorted(lineas.mapped("amount")), [-12.10, 20.0, 50.0])
        uno = lineas.filtered(lambda l: l.amount == 50.0)
        self.assertEqual((uno.partner_name, uno.account_number), ("CLIENTE_01", IBAN_CLIENTE))
        self.assertTrue(all(l.sp_estado != "pendiente" for l in lineas), "El agente ya ha propuesto")
        imp = uno.sp_importacion_id
        self.assertEqual(imp.formato, "PSD2 · Enable Banking")
        self.assertTrue(imp.original_id)
        self.assertEqual(c.cuenta_ids.filtered("journal_id").ultima_fecha, date(2026, 11, 12))
        c._sp_sincronizar()
        self.assertEqual(self.env["account.bank.statement.line"].search_count([("journal_id", "=", self.banco.id)]), 3,
                         "Volver a descargar no duplica")
        ultima = [k for k in self.llamadas if k[1] == "/accounts/u1/transactions"][-1]
        self.assertEqual(ultima[2]["params"]["date_from"], "2026-11-09", "Pide desde la última fecha menos 3 días")
        self.assertFalse([k for k in self.llamadas if k[1] == "/accounts/u2/transactions"], "Sin diario no se descarga")

    def test_limite_del_banco_y_caducidad(self):
        c, _e = self._conectar()
        self.respuestas[("GET", "/accounts/u1/transactions")] = Resp(429, {"error": "ASPSP_RATE_LIMIT_EXCEEDED"})
        c._sp_sincronizar()
        self.assertEqual(c.estado, "activa")
        self.assertIn("se reintentará", c.ultimo_error)
        self.respuestas[("GET", "/accounts/u1/transactions")] = Resp(401, {"error": "EXPIRED_SESSION"})
        c._sp_sincronizar()
        self.assertEqual(c.estado, "caducada")
        self.assertTrue(c.activity_ids)

    def test_aviso_antes_de_caducar_y_caducada(self):
        c, _e = self._conectar()
        self.respuestas[("GET", "/accounts/u1/transactions")] = Resp(200, {"transactions": []})
        c.sudo().valido_hasta = fields.Datetime.now() + timedelta(days=10)
        self.env["sp.banco.conexion"]._sp_cron()
        self.assertTrue(c.aviso_enviado)
        self.assertTrue(c.activity_ids)
        c.sudo().valido_hasta = fields.Datetime.now() - timedelta(minutes=1)
        c._sp_sincronizar()
        self.assertEqual(c.estado, "caducada")

    def test_permisos_y_sin_configurar(self):
        c = self.env["sp.banco.conexion"].with_user(self.conta).create({"name": "BANCO_FICTICIO"})
        with self.assertRaises(AccessError):
            c.with_user(self.otro).action_autorizar()
        with patch.dict(os.environ, {"SP_EB_APP_ID": "", "SP_EB_CLAVE": ""}):
            with self.assertRaises(UserError):
                c.action_autorizar()

    def test_revocar(self):
        c, _e = self._conectar()
        self.respuestas[("DELETE", "/sessions/ses-ficticia")] = Resp(200, {})
        c.with_user(self.conta).action_revocar()
        self.assertEqual(c.estado, "revocada")
        self.assertIn(("DELETE", "/sessions/ses-ficticia"), [(m, r) for m, r, _k in self.llamadas])

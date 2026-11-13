from odoo.tests import new_test_user
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


class SpRecepcionCommon(AccountTestInvoicingCommon):
    """Datos ficticios comunes: dos sedes con su caja, Recepción de cada sede, Contabilidad, ATC y letrado."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.caja = cls.company_data["default_journal_cash"]
        cls.caja_mad = cls.caja.copy({"name": "Caja Madrid (test)", "code": "TCMAD"})
        for caja in (cls.caja, cls.caja_mad):
            for linea in caja.inbound_payment_method_line_ids | caja.outbound_payment_method_line_ids:
                linea.payment_account_id = caja.default_account_id
        cls.sede = cls.env["sp.sede"].create({"name": "Barcelona", "code": "BCN", "journal_id": cls.caja.id})
        cls.sede_mad = cls.env["sp.sede"].create({"name": "Madrid", "code": "MAD", "journal_id": cls.caja_mad.id})
        comunes = {"company_id": cls.env.company.id, "company_ids": [(6, 0, cls.env.company.ids)]}
        def usuario(login, grupos, sede):
            return new_test_user(cls.env, login, groups=grupos, sp_sede_id=sede.id, **comunes)
        cls.recepcion = usuario("test.sp.recepcion", "sp_recepcion.group_sp_recepcion", cls.sede)
        cls.recepcion_mad = usuario("test.sp.recepcion.mad", "sp_recepcion.group_sp_recepcion", cls.sede_mad)
        cls.conta1 = usuario("test.sp.conta1", "sp_recepcion.group_sp_responsable", cls.sede)
        cls.conta2 = usuario("test.sp.conta2", "sp_recepcion.group_sp_responsable", cls.sede)
        cls.atc = usuario("test.sp.atc", "sp_recepcion.group_sp_devolucion_revision", cls.sede)
        cls.letrado = usuario("test.sp.letrado", "sp_recepcion.group_sp_devolucion_letrado", cls.sede)
        cls.cliente = cls.env["res.partner"].create({"name": "CLIENTE_01"})
        cls.cliente2 = cls.env["res.partner"].create({"name": "CLIENTE_02"})

    def _cobro(self, importe=50.0, cliente=None, usuario=None, **extra):
        Pay = self.env["account.payment"].with_user(usuario or self.recepcion).with_context(sp_recepcion=True)
        vals = {"payment_type": "inbound", "partner_type": "customer", "partner_id": (cliente or self.cliente).id,
                "amount": importe, "journal_id": self.caja.id, "sp_tipo": "consulta"}
        vals.update(extra)
        return Pay.create(vals)

    def _cierre(self, contado, usuario=None, notas=False, sede=None):
        return self.env["sp.cierre.caja"].with_user(usuario or self.recepcion).create(
            {"sede_id": (sede or self.sede).id, "contado": contado, "notas": notas})

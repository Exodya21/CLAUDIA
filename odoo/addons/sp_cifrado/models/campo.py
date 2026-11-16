"""Campo de texto cifrado en la base de datos y en claro en el ORM."""
from odoo import fields
from odoo.exceptions import UserError

from .. import cifrado


class CharCifrado(fields.Char):
    """Char que se guarda cifrado (AES-SIV determinista). El ORM lo ve en claro; las búsquedas por igualdad y las
    restricciones de unicidad siguen funcionando porque el mismo texto cifra siempre igual."""

    def convert_to_column(self, value, record, values=None, validate=True):
        value = super().convert_to_column(value, record, values, validate)
        if not value:
            return value
        try:
            return cifrado.cifrar_valor(value)
        except cifrado.SinClave as e:
            raise UserError(str(e)) from e

    def _insert_cache(self, records, values):
        # Lo que viene de la base de datos está cifrado: se descifra al entrar en la caché del ORM.
        return super()._insert_cache(records, map(cifrado.descifrar_valor, values))

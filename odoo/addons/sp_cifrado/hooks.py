"""Al instalar se cifran los IBAN que ya hubiera; al desinstalar se descifran (si no, quedarían ilegibles)."""
import logging

from . import cifrado

_logger = logging.getLogger(__name__)
COLUMNAS = [("res_partner_bank", "account_number"), ("res_partner_bank", "sanitized_account_number"),
            ("account_bank_statement_line", "account_number")]


def _recorrer(env, funcion):
    cr = env.cr
    for tabla, columna in COLUMNAS:
        cr.execute(f'SELECT id, "{columna}" FROM "{tabla}" WHERE "{columna}" IS NOT NULL AND "{columna}" != %s', [""])
        filas = cr.fetchall()
        for rid, valor in filas:
            nuevo = funcion(valor)
            if nuevo != valor:
                cr.execute(f'UPDATE "{tabla}" SET "{columna}" = %s WHERE id = %s', [nuevo, rid])
        _logger.info("sp_cifrado: %s.%s revisadas %s filas", tabla, columna, len(filas))


def _enmascarar_historial(env):
    """El seguimiento estándar guardaba el IBAN completo en el historial: se deja enmascarado."""
    if "mail.tracking.value" not in env:  # Odoo 20 guarda el seguimiento de otra forma; nada que enmascarar aquí
        return
    cr = env.cr
    cr.execute("""SELECT v.id, v.old_value_char, v.new_value_char FROM mail_tracking_value v
                  JOIN ir_model_fields f ON f.id = v.field_id
                  WHERE f.model = 'res.partner.bank' AND f.name = 'account_number'""")
    for vid, viejo, nuevo in cr.fetchall():
        cr.execute("UPDATE mail_tracking_value SET old_value_char = %s, new_value_char = %s WHERE id = %s",
                   [cifrado.enmascarar(viejo) or None, cifrado.enmascarar(nuevo) or None, vid])


def post_init_hook(env):
    if not cifrado.hay_clave():
        raise cifrado.SinClave("No se puede instalar sp_cifrado sin la clave SP_CLAVE_CIFRADO.")
    env.flush_all()
    _recorrer(env, cifrado.cifrar_valor)
    _enmascarar_historial(env)
    env.invalidate_all()


def uninstall_hook(env):
    env.flush_all()
    _recorrer(env, cifrado.descifrar_valor)
    env.invalidate_all()

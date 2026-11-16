# Comprobación del cifrado en la base de datos (después de los demás escenarios). Mira directamente en PostgreSQL y en
# el almacén de archivos, como lo haría quien tuviera una copia de la base: no debe ver IBAN ni extractos en claro.
import re

from odoo.addons.sp_cifrado import cifrado

ok = True
def comprueba(cond, texto):
    global ok
    ok &= bool(cond)
    print(("OK    " if cond else "FALLO ") + texto)

cr = env.cr
cr.execute("SELECT account_number, sanitized_account_number FROM res_partner_bank")
filas = cr.fetchall()
comprueba(filas and all(a.startswith(cifrado.MARCA) and s.startswith(cifrado.MARCA) for a, s in filas),
          f"{len(filas)} cuentas bancarias: IBAN cifrado en la base de datos")
comprueba(not any(re.search(r"ES\d{2}", a + s) for a, s in filas), "Ningún IBAN legible en res_partner_bank")
cuentas = env["res.partner.bank"].search([])
comprueba(all(c.sanitized_account_number.startswith("ES") for c in cuentas), "Odoo los lee en claro a través del ORM")
comprueba(env["res.partner.bank"].search([("account_number", "=", cuentas[0].account_number)]) == cuentas[0],
          "La búsqueda exacta por IBAN funciona")
cr.execute(r"SELECT count(*) FROM mail_message WHERE body::text ~ 'ES\d{2}\s?\d{4}\s?\d{4}\s?\d{4}'")
comprueba(cr.fetchone()[0] == 0, "Ningún IBAN completo en los mensajes del historial")
imps = env["sp.banco.importacion"].search([("original_id", "!=", False)])
claros = 0
for i in imps:
    raw = i.original_id.sudo().raw
    raw = getattr(raw, "content", raw)
    claros += raw.startswith(b"11") or b"TRANSF" in raw  # Norma 43 empieza por el registro 11
comprueba(imps and not claros, f"{len(imps)} extractos originales guardados cifrados en el almacén de archivos")
print("RESULTADO: " + ("todo correcto" if ok else "HAY FALLOS"))

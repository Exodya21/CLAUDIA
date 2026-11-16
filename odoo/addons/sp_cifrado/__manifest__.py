{
    "name": "Despacho · Cifrado de IBAN y documentos",
    "summary": "IBAN cifrados en la base de datos (AES-SIV) y utilidades para guardar documentos cifrados (Fernet). "
               "La clave vive fuera de la base de datos.",
    "description": """
Cifrado en reposo (paso 3 del orden de trabajo, 16/11/2026; referencia: Sistema Propio F5.x, cifrado de columna y
almacén cifrado, documento 08 §3).

- Clave maestra FUERA de la base de datos: variable de entorno SP_CLAVE_CIFRADO (o opción sp_clave_cifrado del
  archivo de configuración de Odoo). Una copia de la base de datos sin la clave no deja leer los IBAN.
- IBAN cifrados: el número de cuenta de las cuentas bancarias (clientes, proveedores, personal y cuentas propias) y el
  IBAN de la contrapartida de los movimientos bancarios se guardan cifrados con AES-SIV (determinista y autenticado).
  Odoo los ve en claro a través del ORM, puede buscar un IBAN exacto y comprobar duplicados; la base de datos solo
  guarda texto cifrado. La búsqueda por trozos se resuelve descifrando en memoria.
- El historial (seguimiento) de cambios del IBAN guarda el IBAN enmascarado (ES12 **** 1234), no completo.
- Utilidades cifrar_archivo / descifrar_archivo (Fernet) para documentos: las usa sp_banco para los extractos
  originales.
- Al instalar se cifran los IBAN que ya hubiera; al desinstalar se descifran.
- Sin clave no se guarda ningún IBAN nuevo (error claro); lo ya cifrado se muestra como «cifrado: falta la clave».
""",
    "version": "20.0.1.0.0",
    "category": "Hidden/Tools",
    "author": "Despacho (desarrollo propio)",
    "license": "LGPL-3",
    "depends": ["account", "mail"],
    "external_dependencies": {"python": ["cryptography"]},
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "installable": True,
}

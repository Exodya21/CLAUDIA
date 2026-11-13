# Puesta en marcha con los datos reales del despacho

Hay **dos instalaciones** con el mismo programa y **bases de datos separadas**. Nunca comparten datos ni documentos.

| | Demostración | Real |
|---|---|---|
| Para qué | Probar y enseñar con datos ficticios | Trabajar con los datos de la empresa |
| Arrancar / apagar | `INICIAR.bat` / `DETENER.bat` | `INICIAR_REAL.bat` / `DETENER_REAL.bat` |
| Claves | `.env` | `.env.real` (cifrado de documentos e IBAN) |
| Copias | `COPIA_SEGURIDAD.bat` → `copias` | `COPIA_SEGURIDAD_REAL.bat` → `copias_real` |
| Acceso | Lista de usuarios demo | Usuario + contraseña + código del móvil |
| Datos ficticios | Sí | **Nunca** |

Las dos usan `http://localhost:3000`: al arrancar una se apaga la otra.

## Antes de meter datos reales (decisión de Dirección, T-60)
- El ordenador debe tener el disco cifrado (BitLocker en Windows) y una sesión con contraseña.
- Haga **una copia diaria** con `COPIA_SEGURIDAD_REAL.bat`.
- Guarde fuera del ordenador, en un USB cifrado o en una nube aprobada, la carpeta `copias_real` **y** el archivo
  `.env.real`. Sin `.env.real` no se pueden leer los documentos ni los IBAN.
- Es una instalación en un solo ordenador. Para que trabaje todo el equipo desde varias sedes hace falta el servidor
  definitivo en la UE (T-02); se migra con una copia de seguridad.

## Primer arranque
1. Doble clic en `INICIAR_REAL.bat`. La primera vez crea las claves, construye el programa (tarda unos minutos) y
   pide estos datos:
   - nombre de la sociedad (como figura en las facturas);
   - sedes (por ejemplo, `Barcelona,Madrid,Valencia`);
   - usuario, nombre y correo de la primera persona de Dirección.
2. Apunte la **contraseña provisional** que aparece. Al entrar la primera vez el programa pide:
   - cambiar la contraseña;
   - activar el código del móvil (Google Authenticator, Microsoft Authenticator…).
3. Abra `.env.real` con el Bloc de notas y escriba el CIF del despacho en la línea `OWN_TAX_IDS=`. Así la lectura de
   facturas no lo confunde con el del proveedor. Vuelva a ejecutar `INICIAR_REAL.bat`.
4. En **Administración → Usuarios** cree las personas del equipo con su rol. Contabilidad necesita una persona con
   rol Contabilidad: Dirección autoriza y aprueba, pero no importa extractos ni registra facturas (separación de
   funciones).

## Bancos: sus 13 cuentas
1. **Contabilidad → Banco y conciliación → Nueva cuenta bancaria.** Rellene nombre, banco, **IBAN completo**, uso,
   actividad y sede. El IBAN se guarda cifrado.
2. **Importar varios extractos a la vez.** Seleccione todos los archivos tal como los descarga de la banca
   electrónica (Excel de Caixa o BBVA, Norma 43, CAMT.053 o CSV). Cada uno va a la cuenta cuyo IBAN termina igual.
   - Si un archivo no indica la cuenta, se avisa: impórtelo desde la propia cuenta.
   - Subir dos veces el mismo extracto no duplica nada.
3. Si un banco no se lee, use **«Comprobar sin importar»**. El error dice qué columnas no reconoce. Envíe a Claude
   **solo la fila de cabecera** (los títulos de las columnas), nunca movimientos.

## Facturas de proveedores
**Contabilidad → Proveedores y facturas.** Seleccione **varias facturas a la vez**: se leen solas una tras otra.
Usted comprueba los datos, da de alta el proveedor si es nuevo (nombre y CIF ya propuestos) y registra. El IVA es
siempre el que figura en la factura.

## Volver a la demostración
`DETENER_REAL.bat` y después `INICIAR.bat`. Los datos reales se quedan en su base y no se mezclan.

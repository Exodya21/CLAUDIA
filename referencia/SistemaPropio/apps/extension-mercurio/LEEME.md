# Extensión «SISTEMA PROPIO · Rellenar Mercurio»

Rellena las pantallas de Mercurio con la **ficha confirmada** de un expediente de SISTEMA PROPIO.
**No firma ni presenta**: no pulsa «Continuar», «Concluir», «Presentación electrónica» ni «Firmar y registrar», no
marca «NO CONSIENTO» y no elige el supuesto de «Tipo de autorización». Eso lo hace siempre el profesional (decisión
T-24, aprobada por Dirección el 05/11/2026).

## Instalar en Chrome (Windows)
1. Descomprima la carpeta `extension-mercurio` en un sitio fijo (p. ej. `C:\SistemaPropio\extension-mercurio`).
2. Abra Chrome y escriba en la barra `chrome://extensions`.
3. Active **Modo de desarrollador** (arriba a la derecha).
4. Pulse **Cargar descomprimida** y elija esa carpeta.
5. Fije el icono «SP» en la barra (icono de la pieza de puzle → chincheta).

Si SISTEMA PROPIO no está en `http://localhost:3000` (p. ej. en un servidor del despacho), abra la extensión →
«Ajustes y diagnóstico» → escriba la dirección y pulse «Guardar dirección».

## Uso
1. En SISTEMA PROPIO, en el expediente: revise la **ficha de datos del formulario**, pulse «Guardar ficha» y después
   «Rellenar en Mercurio». Aparece un código `XXXX-XXXX-XXXX` (caduca a los 15 minutos, solo vale para ese expediente).
2. En Mercurio (acceso Abogacía → Continuar presentación → Presentar nueva solicitud) abra el modelo.
3. Pulse el icono «SP», escriba el código y pulse **Traer datos**.
4. En cada pestaña de Mercurio pulse **Rellenar esta página**:
   - **verde**: rellenado; **amarillo**: Mercurio lo pide pero la ficha no lo tiene; **rojo**: el valor no está en la lista.
   - Lo que ya estaba escrito no se toca (salvo que marque «Sustituir lo que ya esté escrito»).
   - En «Municipio» y «Localidad» la extensión espera a que Mercurio cargue la lista tras la provincia.
5. Revise, pulse usted «Continuar» y repita en la siguiente pestaña. Adjunte los documentos del paquete, firme con
   AutoFirma y presente. Después suba el resguardo al expediente.
6. Al terminar pulse **Olvidar datos** (también se borran solos al cerrar Chrome o al caducar el código).

## Privacidad y seguridad
- Solo funciona en `mercurio.delegaciondelgobierno.gob.es`; solo pide el permiso de almacenamiento.
- Los datos se guardan en la memoria de la sesión del navegador (no en disco) y se borran al caducar el código.
- El código no da acceso a nada más que a la ficha confirmada de un expediente; cada lectura queda en la auditoría.
- **Diagnóstico**: «Copiar estructura de esta página (sin datos)» copia solo etiquetas y tipos de campo de Mercurio,
  nunca lo escrito. Sirve para ajustar el reconocimiento si Mercurio cambia.

## Cómo reconoce los campos
1. **Por el identificador interno de Mercurio** (versión 0.2, a partir del diagnóstico real del EX-10 del 05/11/2026):
   `ext…` extranjero/a, `rea…Reagrupante` familiar, `emp…Empresa` empleador, `emp…Empresa2` centro de formación,
   `pre…Presentador` presentador y `not…Notificacion` notificaciones. Así un solo clic rellena todas las pestañas.
2. Por la etiqueta y el apartado, como respaldo, solo en la pestaña visible.

## Datos del empleador (F4.3)
Desde la versión de SISTEMA PROPIO con lectura de documentos, la ficha trae los datos del contrato. La extensión
rellena por identificador la empresa (nombre, NIF, domicilio, representante); **cuenta de cotización, código de
contrato y centro de trabajo** se escriben a mano en Mercurio hasta recibir el diagnóstico de esa pestaña (T-29).

## Estado de las pruebas
Probada en Chrome con una **página de prueba inventada** (`pruebas/formulario_prueba.html`) que imita la disposición
vista en capturas de Mercurio. Los identificadores salen de la estructura real de Mercurio (EX-10), pero **el relleno completo aún no se ha visto
funcionar en Mercurio real**: pruébelo con un expediente de datos inventados, sin presentar (salga con «Volver»), y
envíe el diagnóstico si algún campo queda sin rellenar.

## Actualizar la extensión
Sustituya los archivos de la carpeta por los nuevos y, en `chrome://extensions`, pulse el botón de recargar (↻) de la
tarjeta «SISTEMA PROPIO · Rellenar Mercurio».

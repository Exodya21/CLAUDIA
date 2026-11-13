# 15 · Manual del usuario

Sistema Propio · versión F5.6 · 12/11/2026. Cada persona ve solo los módulos y botones que su rol permite. Si algo no
aparece, no es un fallo: pídalo a Dirección.

## 1. Entrar y salir
1. Abra la dirección del sistema en Chrome o Edge.
2. Escriba su usuario y su contraseña. Después, el **código de 6 dígitos** de la aplicación del móvil.
3. La primera vez:
   1. Cambie la contraseña (mínimo 12 caracteres).
   2. Active el código: escanee el QR, o pulse «Introducir clave de configuración» en la aplicación, con nombre
      `Sistema Propio`, la clave que se muestra y tipo «Basado en tiempo».
4. La sesión se cierra sola tras 60 minutos sin actividad y, en todo caso, a las 8 horas.
5. En **Ajustes → Mis sesiones** puede cerrar la sesión de otro equipo.

**Menú:** Inicio, Clientes, CRM, Expedientes, Extranjería, Agenda, Comunicaciones, Economía, Gastos, Recepción,
Contabilidad, RRHH, Administración y Ajustes.
- Los módulos marcados **«No disponible aún»** (Citas, Fichas laborales, Documentos, Facturación, Dirección) todavía
  no funcionan, y lo indican.
- **«En curso»** quiere decir que el módulo funciona pero le falta una fase.

## 2. Clientes
- **Buscar:** por nombre, documento o teléfono. Recepción y Atención al cliente ven los datos **enmascarados**.
- **Nuevo cliente:** nombre, apellidos, documento (se comprueba la letra de control), teléfono y correo.
  - Si el sistema avisa de un **posible duplicado**, revíselo: puede ser la misma persona.
  - Un teléfono compartido no significa que sean la misma persona. Nunca se unen automáticamente.

## 3. CRM
1. **Nuevo lead:** cliente + **origen** (obligatorio) + interés.
2. Avance con los botones: contactado, en seguimiento, cita solicitada.
3. «Descartado» y «No convertido» piden el motivo.
4. Al abrir un expediente, el lead pasa solo a «Convertido».

## 4. Expedientes
1. **Abrir:** cliente, área (Laboral o Extranjería), título. El código se asigna solo (`LAB-2026-0001`).
2. **Asignar** personas (letrado, asesor, gestor).
3. **Estados:** solo aparecen los cambios que su rol permite. Resolver, archivar o desistir es solo para letrados.
4. Nada se borra; un expediente se archiva o se desiste.

## 5. Agenda
- **Nueva tarea:** expediente, responsable, fecha.
  - Los señalamientos y las conciliaciones llevan hora de inicio y fin. Si se solapan con otra tarea suya, se avisa.
- **Aplazar** pide un motivo.
- **Plazo legal:** escriba la fecha y su fuente. Quedará «pendiente de validar» hasta que un letrado la confirme.
  El sistema no calcula plazos.

## 6. Extranjería
1. **Abrir expediente:** elija el trámite. Se cargan los documentos requeridos y la fuente oficial.
2. **Subir documentos:** pasaporte, contrato, padrón, TIE, tasa, etc. El sistema los **lee** y propone datos.
3. **Validar:** marque cada documento como válido. Solo los documentos válidos pasan datos a la ficha.
4. **Ficha EX:** revise y guarde los datos. Si un documento dice algo distinto de lo guardado, se avisa, pero no se
   sobrescribe.
5. **Mercurio:**
   1. Pulse «Preparar para Mercurio». Obtendrá un código de 15 minutos.
   2. En Chrome, con la extensión instalada, abra el formulario de Mercurio y pegue el código.
   3. La extensión **rellena los campos**.
   4. **Usted** revisa, marca el consentimiento y presenta. La extensión nunca presenta.
6. **Fases:** registre «Presentado», «Requerimiento», etc. Un requerimiento crea una tarea de plazo sin fecha, que fija
   el letrado.

## 7. Comunicaciones (portal del cliente)
- En el expediente, pestaña **Conversación**: escriba al cliente, siempre **de usted**. Puede corregir un mensaje
  durante 15 minutos; después, solo ocultarlo con motivo.
- **Invitar al portal:** el cliente recibe un correo y entra con un código.
- **Aviso urgente:** solo con plantilla y con la fecha de una tarea del expediente.
- Los mensajes automáticos que proponga el sistema aparecen en «Pendientes de decidir».

## 8. Recepción
1. **Cobrar:** busque el cliente y el expediente (o «consulta» si aún no tiene). Indique importe y forma de pago.
   - Si se parece a otro cobro reciente, el sistema avisa. Para seguir, explique el motivo.
2. **Justificante:** se genera en PDF. **No es una factura.**
3. **Cierre de caja** al final del día: cuente el efectivo. Lo valida **otra** persona.
4. **Devoluciones:** regístrelas con el motivo. Las aprueba Contabilidad.

## 8b. Recepción en Odoo 20
Menú **Contabilidad → Recepción** (módulo `sp_recepcion`; 19 §3.1). Ejemplos con datos ficticios.
1. **Cobrar:** *Cobros → Nuevo*. Indique el cliente (p. ej. CLIENTE_01), el importe, la caja de su sede, el **tipo**
   (consulta, provisión de fondos, servicio u otro) y, si la hay, una referencia. Pulse **Confirmar**.
   - Si se parece a otro cobro reciente, el sistema lo indica y no lo registra. Si no es repetido, explique el motivo
     (mínimo 10 caracteres) en «Motivo (posible cobro repetido)» y vuelva a pulsar **Confirmar**. Contabilidad
     recibirá un aviso para revisarlo.
2. **Imprimir el justificante:** botón **Justificante**. Tiene un número de su sede (p. ej. `REC-BCN-2026-000001`).
   Se genera una sola vez y siempre se imprime igual. **No es una factura.**
3. **Confirmar (Contabilidad):** el responsable revisa los cobros «Pendientes de confirmar» y pulsa **Confirmar
   (Contabilidad)**. Si hay que anular un cobro, lo hace el responsable con **Anular cobro**, explicando el motivo. No
   se puede anular si la caja de ese día ya está validada, y un cobro nunca se borra.
4. **Cerrar la caja:** al final del día, *Cierres de caja → Nuevo*. Elija la sede y el día, escriba el **efectivo
   contado** y pulse **Registrar recuento**. El sistema calcula lo que debería haber; si no coincide, explique la
   diferencia en «Notas del recuento».
5. **Validar el cierre (Contabilidad):** **otra persona**, responsable de caja, abre el cierre y pulsa **Validar
   cierre** o **Rechazar** (con una nota). Si hay diferencia, al validar se registra el ajuste. Un cierre validado no
   se modifica. Si se rechaza, se puede contar de nuevo.

## 9. Gastos
1. «Nuevo gasto» → suba la foto o el PDF del ticket.
2. El sistema propone importe, fecha y comercio. Compruébelos.
3. Elija la forma de pago (caja, tarjeta de empresa o personal) y envíe.
4. Si se lo devuelven, corrija y vuelva a enviar.

## 10. Contabilidad
Pestañas: **Rutina · Banco y conciliación · Proveedores y facturas · Tesorería · Cierre · Informes · Pendientes**.

- **Rutina:** lo que toca hoy, esta semana y este mes.
  - Los pasos se marcan solos cuando el sistema comprueba que están hechos.
  - Si un paso no procede, pulse «No aplica» y explique por qué.
- **Banco:**
  - «Importar varios extractos»: seleccione todos los archivos tal como los descarga del banco (Excel, Norma 43,
    CAMT o CSV). Cada uno va a su cuenta por el IBAN.
  - «Comprobar sin importar» le dice si un archivo se puede leer, sin guardar nada.
  - **Conciliar:** el sistema propone a qué cobro o factura corresponde cada movimiento y por qué. Usted acepta o
    corrige.
- **Facturas:**
  1. Seleccione varias facturas a la vez; se leen solas.
  2. Compruebe proveedor, número, fecha, base, IVA, retención y total.
  3. Si el proveedor es nuevo, «Alta rápida» (nombre y CIF ya propuestos).
  4. Registre y después valide.
  - El IVA es siempre el que figura en la factura.
- **Tesorería:**
  1. Proponga una remesa con las facturas validadas.
  2. Dirección la firma dos veces.
  3. Descargue el fichero SEPA y súbalo **usted** a la banca electrónica.
- **Cierre:**
  1. Prepare el cierre del mes.
  2. Revise las desviaciones.
  3. Dirección lo aprueba.
- **Informes:** semanal, quincenal y mensual, en pantalla, PDF y CSV.

Guía de prueba paso a paso: `docs/pruebas/guia_manual_contabilidad.md` (28 pasos).

## 11. RRHH
- **Mi ficha** (todos): sus datos, documentos y ausencias. Solicite vacaciones o permisos; RRHH los aprueba y quedan
  en la Agenda.
- **RRHH:**
  - fichas del personal y carpeta de documentos;
  - subir nóminas (se leen y se confirman si cuadran);
  - aprobar ausencias.
  - El salario solo lo ven RRHH y la propia persona.

## 12. Pendientes de decidir
En cada departamento verá una lista de **propuestas del sistema**: conciliaciones, mensajes, revisiones de caja,
remesas por firmar, informes por revisar, etc.
- Cada propuesta explica el motivo.
- «Aceptar» ejecuta la acción. «Rechazar» la descarta y no vuelve a aparecer.

## 13. Buenas prácticas
- No comparta su contraseña ni su código. No haga capturas del QR.
- Bloquee el equipo al levantarse (Windows + L).
- No descargue documentos de clientes en equipos personales.
- Si ve datos que no debería ver, avíselo a Dirección.

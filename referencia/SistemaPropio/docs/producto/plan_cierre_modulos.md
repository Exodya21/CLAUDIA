# Plan para cerrar los módulos pendientes (09/11/2026)

Estado honesto de cada módulo del menú y orden propuesto. Los módulos «operativos» están construidos de verdad:
base de datos, API, permisos, pantallas, pruebas y auditoría. «En curso» significa que funcionan, pero tienen una
fase pendiente.

| Módulo | Estado | Qué falta | Depende de una decisión externa |
|---|---|---|---|
| Clientes, CRM, Expedientes, Agenda, Gastos | Operativo | — | — |
| Extranjería (expediente, ficha EX, extensión Mercurio, lectura de documentos) | Operativo | Notificaciones DEHú (fase 3) | T-25, T-26 |
| Comunicaciones (portal del cliente) | En curso | SMS/push para avisos urgentes | T-33 (correo), T-35 (SMS) |
| Economía y Recepción | En curso | Citas y llegada a recepción, agente que clasifica | D-11, D-19 (configurables) |
| **Contabilidad** | **Operativo** | Asientos contables | **T-40** (plan de cuentas de la gestoría) |
| RRHH | En curso | Control horario, formación, cuadro de mando | T-41 (sistema de fichaje actual) |
| **Citas** (M03) | Pendiente | Todo: agenda de citas propia, confirmaciones por el portal, llegada | D-11, D-19 configurables: **se puede construir ya** |
| **Dirección** (cuadro de mando) | Pendiente | Panel con cifras de todos los departamentos | No: **se puede construir ya** con los datos existentes |
| **Documentos** (gestor general) | Pendiente | Carpeta documental por cliente y expediente con versiones y búsqueda | No: **se puede construir ya** (reutiliza el almacén cifrado) |
| **Fichas laborales** (superficha M04) | Pendiente | Las 3 rutas de preguntas, lectura de nómina/contrato/vida laboral | Acuerdos U-01…U-18 «para validación final» |
| **Facturación** (emitir facturas) | Pendiente | Emitir facturas a clientes | **D-07 VeriFactu**: por ley, el programa que emite facturas debe estar certificado. Propuesta: conectar un programa homologado (comparativa D-25 entregada); el sistema le pasa los datos y guarda la referencia |

## Orden propuesto
1. **F5.6 Puesta en marcha real** (hecho hoy): instalación real separada, 13 cuentas con IBAN, varios extractos y
   varias facturas a la vez.
2. **Dirección**: cuadro de mando con cifras de Contabilidad, Recepción, RRHH, Comunicaciones y Expedientes, y avisos.
3. **Citas**: agenda de citas por sede y asesor, confirmación y recordatorio por el portal, llegada a recepción y
   cobro de la consulta.
4. **Documentos**: carpeta única por cliente y expediente, versiones, búsqueda y permisos.
5. **Fichas laborales**: las tres rutas, una vez validados U-01…U-18 (se puede construir antes como propuesta).
6. **Facturación**: conexión con el programa homologado que elija Dirección (D-25).

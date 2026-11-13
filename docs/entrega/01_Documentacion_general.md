# 01 · Documentación general del sistema

Sistema Propio · versión F5.6 · 12/11/2026

## 1. Qué es
Sistema Propio es la plataforma jurídica y de gestión del despacho del abogado Rafael Serrano (España, con una entidad
de soporte en Colombia). Sustituye progresivamente a **MNProgram (MNP)** y a herramientas sueltas: hojas de cálculo,
WhatsApp personal, cajas en papel.

Reúne en un solo sistema, con un único registro de cada persona:
- captación de clientes (CRM);
- expedientes laborales y de extranjería;
- agenda y plazos;
- portal del cliente y comunicaciones;
- recepción y cobros (control no fiscal);
- banco, contabilidad de proveedores, tesorería y cierre mensual;
- recursos humanos;
- auditoría completa.

## 2. Para quién
47 personas usuarias aproximadamente, en varias sedes, repartidas en 12 roles (ver 08 · Seguridad). Los clientes
entran por un portal separado.

> **Nota (13/11/2026):** la cifra de 47 es la del charter e incluye al empleado del autónomo del titular, que queda
> fuera de Odoo (18 · AL-06). En Odoo se gestionan **46 personas**.

| Departamento | Uso principal |
|---|---|
| Dirección | Visión global, aprobaciones, informes, administración |
| Laboral | Expedientes laborales, agenda |
| Extranjería | Expedientes de extranjería, ficha del modelo EX, preparación para Mercurio |
| Recepción y Atención al cliente | Contactos, citas, cobros, caja |
| Contabilidad | Banco, facturas recibidas, pagos, cierre, informes |
| RRHH | Personal, nóminas (lectura), ausencias |
| Marketing | Leads y embudo |
| Soporte Colombia | Tareas asignadas, en su propia entidad |

## 3. Estado de los módulos (12/11/2026)
| Módulo | Estado | Pendiente |
|---|---|---|
| Clientes y contactos | **Operativo** | — |
| CRM (leads y embudo) | **Operativo** | — |
| Expedientes | **Operativo** | — |
| Agenda, tareas y plazos | **Operativo** | Plazos legales automáticos: no se implementan sin fuente legal y revisión (T-25, T-26) |
| Extranjería (expediente, ficha EX, extensión Mercurio, lectura de documentos) | En curso (fases 1 y 2 operativas) | Notificaciones DEHú y plazos (fase 3, T-25, T-26) |
| Gastos de empresa | **Operativo** | — |
| Contabilidad (banco, conciliación, facturas recibidas, remesas SEPA con doble firma, cierre del mes, rutina e informes) | **Operativo** | Asientos contables (T-40, plan de cuentas de la gestoría) |
| Comunicaciones (portal del cliente) | En curso | SMS/push y WhatsApp/Callbell (T-31, T-35) |
| Economía y Recepción | En curso | Citas y llegada a recepción |
| RRHH | En curso | Control horario (T-41), formación, cuadro de mando |
| Citas, Dirección (cuadro de mando), Documentos (gestor general) | Pendiente | Se pueden construir ya |
| Fichas laborales (superficha, 3 rutas) | Pendiente | Validación U-01…U-18 |
| Facturación a clientes | Pendiente | **D-07 VeriFactu**: el programa que emite facturas debe estar certificado. En Odoo, decidido el 13/11/2026: emite Odoo con Verifactu (18 · AL-03, 19 §1.3) |

«Operativo» quiere decir que el módulo tiene base de datos, API, permisos, pantallas, pruebas automáticas y auditoría.
Los módulos pendientes aparecen en el menú como **«No disponible aún»**: no hay pantallas simuladas.

## 4. Reglas que no se pueden romper
Estas reglas vienen de la Dirección y de la documentación del proyecto. Cualquier reimplementación, también en Odoo,
debe mantenerlas.
1. **Datos ficticios en desarrollo.** Nunca expedientes, nóminas o pasaportes reales en pruebas, registros,
   repositorio ni herramientas de IA externas.
2. **Permisos reales en el servidor**, por entidad, sede, departamento, rol y asignación. Se deniega por defecto.
   Ocultar algo en pantalla no cuenta como seguridad.
3. **Auditoría** de ediciones, accesos y descargas, con usuario y fecha, inmutable.
4. **Sin reglas legales o fiscales fijas en el código** sin fuente legal vigente y revisor profesional. Esto incluye
   plazos, nacionalidad, FOGASA, firma, facturación y portales oficiales.
5. **La IA y los agentes proponen; las personas deciden.** Nada determina derechos, plazos o resultados, y nada se
   presenta de forma autónoma.
6. **Una persona = un contacto maestro**, con N expedientes. Nunca se fusiona automáticamente por teléfono.
7. **Trato de usted** en todo lo que ve el cliente. No se ofrecen reservas de citas biométricas.
8. **Secretos fuera del código**, en variables seguras o un gestor de secretos.
9. **Canales judiciales y administrativos** (Mercurio, DEHú, LexNET): ni envío ni descarga automática sin interfaz
   autorizada y autorización del profesional.
10. **Sin borrado físico** de expedientes, contactos ni registros con valor de prueba: se anulan o se sustituyen.
11. **No se emiten facturas ni se calcula IVA** (D-05, D-07, D-16, D-18, D-25). El IVA de una factura recibida es
    siempre el que figura en ella.
    **En el sistema en Odoo aplica la decisión 18 · AL-03 (13/11/2026):** Odoo 20 Community emite las facturas de
    venta con Verifactu (`l10n_es_edi_verifactu`) y calcula el IVA de **sus** facturas. Las facturas recibidas siguen
    con el IVA que figura en ellas. Los módulos propios no alteran el registro, el encadenamiento, la numeración ni el
    envío de Verifactu (19 §1.3). Esta regla 11 sigue vigente tal cual para Sistema Propio.

## 5. Requisitos de origen
El alcance procede de cinco fuentes, con trazabilidad individual (ver 17 · Auditoría y trazabilidad):
- 120 procesos de automatización (I-001…I-120);
- 70 necesidades del documento Qubiq/Odoo (Q-1.1…Q-6.23);
- acuerdos de la superficha laboral (U-01…U-18);
- la matriz maestra de 208 referencias;
- el plan maestro de arquitectura.

## 6. Entidades y sedes
- Dos entidades legales separadas: **España** y **Colombia**. Un usuario de una no ve nada de la otra.
- **Nota (13/11/2026):** el charter de QUBIQ cita una tercera entidad, el **autónomo del titular**. Queda **fuera de
  Odoo**: no es compañía, no emite con Verifactu en Odoo y sus facturas a la S.L. se registran como facturas de
  proveedor. Decidido provisionalmente; falta que lo confirme la gestoría (18 · AL-06).
- Las sedes (por ejemplo Barcelona, Madrid, Valencia) se configuran en la instalación.

## 7. Cómo se ha construido
- Por incrementos (F0.1 → F5.6). Cada uno se entrega con migración, API, pantallas, permisos, pruebas y evidencias.
- Hay dos instalaciones con el mismo programa:
  - **demostración**, con datos ficticios;
  - **real**, con los datos del despacho, en un ordenador protegido hasta que esté listo el servidor.
- El servidor definitivo está comprado. La estructura destino es **Odoo Community** (ver 02 · Arquitectura, apartado 8):
  **Odoo 20.0 Community para todo el proyecto**, decidido el 13/11/2026 (18 · AL-01, AL-02 y criterio de 18 §2).

## 8. Glosario
| Término | Significado |
|---|---|
| Entidad | Empresa o sociedad (España, Colombia) |
| Expediente | Asunto de un cliente con código consecutivo (LAB-2026-0001, EXT-2026-0001) |
| Contacto maestro | Ficha única de una persona |
| Agente | Proceso automático que revisa datos y **propone** acciones en «Pendientes de decidir» |
| Justificante | Recibo no fiscal de un cobro (no es una factura) |
| Remesa | Conjunto de pagos a proveedores con doble firma y fichero SEPA |
| Mercurio | Plataforma de extranjería del Ministerio; la extensión del sistema la rellena, pero nunca presenta |
| MNP | MNProgram, el programa actual que se sustituye |
| T-nn / D-nn | Decisiones del proyecto (`docs/producto/decisiones.md`) |

# 18 · Alineación con el Project Charter de QUBIQ

Sistema Propio · 13/11/2026

Este documento compara la documentación de Sistema Propio (documentos 01 a 17) con el *Project Charter* de QUBIQ del
08/09/2026, que es el alcance acordado para Odoo. Recoge **en qué no coinciden** y qué hay que decidir. Mientras un
punto siga abierto, **no se resuelve en el código ni en la configuración**: lo decide la Dirección y se anota aquí.

El resumen del charter está en la skill `.claude/skills/sistema-odoo-despacho/`. La comparativa por necesidad (fase,
Community y Enterprise) está en `documentacion/Odoo 20 - Community vs Enterprise por fase.xlsx`.

## 1. Diferencias que hay que decidir
| ID | Tema | Sistema Propio (01–17) | Charter de QUBIQ | Qué hay que decidir | Estado |
|---|---|---|---|---|---|
| AL-01 | Edición de Odoo | **Community**, por decisión de la Dirección (01 §7, 02 §8) | Da por hechas apps **Enterprise**: Citas, Firma, Documentos, Helpdesk, WhatsApp, VoIP, intercompañía, sincronización bancaria, activos, SEPA… | Community con OCA y módulos `sp_*`, o Enterprise. Afecta sobre todo a la Fase 1 (8 de 24 necesidades no están en Community) | Abierto |
| AL-02 | Versión de Odoo | 17.0 o 18.0 (04) | Odoo **v20** (necesidad 1.3) | Fijar la versión. La 20.0 Community existe y se ha probado con Facturación (13/11/2026). Los módulos de OCA hay que comprobarlos en la versión elegida | Abierto |
| AL-03 | Facturación a clientes | No se emiten facturas ni se calcula IVA hasta tener un sistema conforme con VeriFactu (01 §4 regla 11, D-07) | Odoo factura y envía a VeriFactu (4.1, 4.2) | Si se acepta el módulo de Odoo (`l10n_es_edi_verifactu`, presente en Community 20) como sistema de facturación. Hay que comprobar la declaración responsable del fabricante del software | Abierto |
| AL-04 | Plazos legales | No hay plazos automáticos sin una fuente legal vigente y la revisión de un profesional (01 §4 regla 4, T-25, T-26) | Fija las cifras: despido a 20 días hábiles, papeleta a 15 y 20, pruebas 12 días antes del juicio, ejecución a 2 y 9 meses, FOGASA a 90, 180, 270 y 330 días (6.9–6.12) | Que un abogado valide cada plazo con su fuente legal y se registre como decisión antes de programarlo | Abierto |
| AL-05 | Automatismos hacia el cliente | Los agentes **proponen** y las personas deciden; nada se presenta solo (01 §4 regla 5) | Envíos automáticos de WhatsApp o correo, cambios de etapa y creación de oportunidades (2.9, 3.2, 6.3, 6.10) | Qué envíos automáticos se permiten sin validación de una persona | Abierto |
| AL-06 | Entidades | Dos: España y Colombia (01 §6) | Tres: la S.L., la filial de Colombia y el **autónomo del titular**, que también factura (1.1, 4.2) | Si el autónomo es una compañía aparte en Odoo | Abierto |
| AL-07 | Código de expediente | `LAB-2026-0001`, `EXT-2026-0001` (01 §8) | `EXP-LAB-2026-001`, `EXP-EXT-2026-001` (6.2) | Formato definitivo; afecta a la migración desde MNP | Abierto |
| AL-08 | Requisitos de QUBIQ trazados | 70 (Q-1.1…Q-6.23 y Q-6.20B) (17 §2) | El charter actual tiene **77** necesidades (incluye la 6.24 y la 6.25) | Actualizar la matriz de trazabilidad con la versión vigente del charter | Abierto |
| AL-09 | Firma | Pendiente de decisión (firma cualificada); `sign_oca` en Community (02 §8.1) | Odoo Sign con enlace único, PDF/A con OCR y certificado adjunto (6.6, 6.7) | Herramienta y nivel de firma | Abierto |
| AL-10 | WhatsApp | Conector propio con la API de Callbell (T-31) | WhatsApp de Odoo (Enterprise) con plantillas (2.2, 3.3) | Callbell más conector propio, o WhatsApp de Odoo | Abierto |
| AL-11 | Contactos duplicados | Nunca se fusiona automáticamente (01 §4 regla 6) | Importación «desduplicada» de los más de 100.000 contactos (4.12) | Regla de desduplicación en la migración: solo aviso, o fusión revisada | Abierto |
| AL-12 | Conciliación bancaria | Propuestas explicadas, nunca automática (02 §8.1) | Odoo propone y solo se revisa a mano lo imprevisto (4.5) | Si se permite la conciliación automática con reglas | Abierto |
| AL-13 | Plan de cuentas | Asientos pendientes del plan de la gestoría (T-40) | Suplidos en 554/555 (4.8) y cuenta de mediación para el 80 % (4.7) | Cerrar el plan de cuentas con la gestoría | Abierto |

## 2. Piezas de este repositorio y su relación con Sistema Propio
| Pieza | Dónde | Relación |
|---|---|---|
| Super Ficha Laboral (prototipo) | `super_ficha_laboral.html`, `fuente/`, `LEEME_TRASPASO.md` | Es la «Ficha laboral (superficha)» que el documento 01 §3 da como pendiente (U-01…U-18). Cubre las necesidades 6.1, 6.8 y 6.9 del charter |
| Convenios colectivos | `convenios/`, skills `convenio-*` | Apoyo a la ficha B y a la papeleta |
| Prueba de Odoo 20 Community con Facturación | `documentacion/odoo20_facturacion_demo/` | Capturas con datos ficticios: series, IVA y retención de IRPF |
| Comparativa Community/Enterprise | `documentacion/Odoo 20 - Community vs Enterprise por fase.xlsx` | Base para decidir AL-01 |

## 3. Cómo se cierra un punto
1. La Dirección (o la persona en quien delegue) decide.
2. Se cambia el **Estado** a «Decidido · fecha · quién» y se resume la decisión en la fila.
3. Se actualizan los documentos afectados (01–17) y se añade la entrada correspondiente en 11 · Changelog.

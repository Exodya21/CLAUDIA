---
name: documentacion-proyecto
description: Documentación viva del proyecto (Sistema Propio y su paso a Odoo) en docs/entrega/. Úsala para CONSULTAR cualquier cosa del sistema (módulos, reglas, base de datos, permisos, API, instalación, decisiones, incidencias, estado) y, sobre todo, para ACTUALIZAR la documentación al terminar cualquier trabajo del proyecto: cambios, pruebas, incidencias, decisiones, instalaciones, configuraciones de Odoo, nuevas piezas en el repositorio. Si se ha hecho algo del proyecto y no se ha documentado, el trabajo no está terminado.
---

# Documentación del proyecto (`docs/entrega/`)

La documentación del sistema del despacho vive en `docs/entrega/`.

- **El Markdown es la fuente.** Los Word de `docs/entrega/word/` se generan a partir de él. Nunca se editan los Word a
  mano.
- `docs/entrega/openapi.json` es la especificación de la API de Sistema Propio (versión F5.6).
- El alcance acordado con QUBIQ está en la skill `sistema-odoo-despacho`. Las diferencias entre los dos están en el
  documento **18**.

## Dónde buscar
| Pregunta | Documento |
|---|---|
| Qué es el sistema, estado de los módulos, reglas que no se pueden romper, glosario | 01 |
| Arquitectura y **correspondencia con Odoo Community** (OCA, módulos `sp_*`, riesgos) | 02 §8 |
| Servidor, red, copias y entornos | 03, 13 |
| Tecnologías y su equivalente en Odoo | 04 |
| Qué hace cada módulo y sus reglas de negocio | 05 |
| Estructura del código y convenciones | 06 |
| Tablas y columnas | 07 |
| Roles, matriz de permisos, 2FA y cifrado | 08 |
| Instalación (Windows, Linux, Odoo, Odoo 20 de pruebas) | 09 |
| Pruebas y criterios de aceptación | 10 |
| Qué ha cambiado y cuándo | 11 |
| Problemas ya vistos y su solución | 12 |
| Manuales de administración y de usuario | 14, 15 |
| Rutas de la API e integraciones | 16, `openapi.json` |
| Auditoría y trazabilidad de requisitos (I-, Q-, U-) | 17 |
| Diferencias con el charter de QUBIQ y decisiones pendientes (AL-nn) | 18 |

Para consultar, busca con Grep en `docs/entrega/*.md` y cita el documento y el apartado (p. ej. «01 §4 regla 11»).
Si algo no está documentado, dilo; no lo supongas.

## Reglas que hay que respetar siempre (01 §4)
Datos ficticios en desarrollo · permisos en el servidor, denegados por defecto · auditoría inmutable · sin reglas
legales o fiscales fijas sin fuente y revisión · la IA propone y las personas deciden · una persona = un contacto
maestro, sin fusiones automáticas · trato de usted al cliente · secretos fuera del código · sin envíos automáticos a
canales judiciales · sin borrado físico · no se emiten facturas hasta que se decida AL-03.

Si una petición choca con una de estas reglas o con un punto abierto del documento 18, avisa antes de hacerla.

## Cómo actualizar al terminar un trabajo
Haz esto en el mismo trabajo, no después:

1. **11 · Changelog:** añade una entrada **arriba**, con el formato `## [ID] · dd/mm/aaaa — título` y los apartados
   `### Añadido`, `### Cambiado`, `### Corregido` o `### Comprobado`. Usa `F…` para las versiones de Sistema Propio y
   `DOC-n` para el trabajo de documentación y evaluación.
2. **12 · Incidencias:** cada problema encontrado va con un ID nuevo (el siguiente libre de su apartado) y las
   columnas fecha · síntoma · causa · solución · prevención. Si la causa no está comprobada, dilo así.
3. **18 · Alineación:** si se decide un punto AL-nn, cambia su estado a «Decidido · fecha · quién» y actualiza los
   documentos que afecte. Si aparece una diferencia nueva con el charter, añade un AL- nuevo.
4. **El documento temático** que corresponda (05 funcional, 07 base de datos, 08 permisos, 09 instalación, 15
   manual…), si el trabajo cambia lo que describe.
5. **00 · Índice:** solo si se añade un documento.
6. **Regenera los Word** de los documentos tocados:
   `python3 herramientas/docs_a_word.py 11 12 18` (prefijos) o, sin argumentos, todos.
7. Guarda los cambios en git (commit) con un mensaje que diga qué se documentó.

## Estilo
- Español claro, frases cortas y tablas cuando haya más de dos elementos que comparar.
- Fechas en formato dd/mm/aaaa.
- **Sin datos personales:** nada de nombres de clientes o empleados, DNI/NIE, IBAN, teléfonos ni claves. Usa
  CLIENTE_01, EXPEDIENTE_01, EMPLEADO_01.
- Distingue lo **comprobado** (en el código o en una prueba) de lo **supuesto** o de lo que debe confirmar otra persona.

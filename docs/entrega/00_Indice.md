# Documentación de entrega · Sistema Propio

Despacho Rafael Serrano · versión **F5.6** · 12/11/2026 · Destinatarios: equipo de programación

Este paquete describe el sistema **tal como está construido y probado** (código en `apps/`, 229 endpoints, 78 tablas,
254 pruebas de API) y cómo trasladarlo a **Odoo Community**, la plataforma elegida para el servidor definitivo. Los
documentos que salen del código (base de datos, permisos, API, pruebas, cambios) se han generado a partir de él, así
que coinciden con lo entregado.

| Nº | Documento | Contenido principal |
|---|---|---|
| 01 | [Documentación general del sistema](01_Documentacion_general.md) | Qué es, alcance, módulos, estado, reglas que no se pueden romper |
| 02 | [Arquitectura](02_Arquitectura.md) | Monolito modular, capas, flujos, eventos y agentes. **Correspondencia con Odoo Community** |
| 03 | [Infraestructura TI](03_Infraestructura_TI.md) | Servidor, red, contenedores, copias, entornos, requisitos del servidor nuevo |
| 04 | [Stack tecnológico](04_Stack_tecnologico.md) | Tecnologías y versiones; equivalencia en Odoo |
| 05 | [Documentación funcional y lógica](05_Funcional_y_logica.md) | Cada módulo: qué hace, reglas de negocio, estados y lo que nunca hace |
| 06 | [Documentación técnica y del código](06_Tecnica_y_codigo.md) | Estructura del repositorio, convenciones, cómo añadir funciones |
| 07 | [Base de datos](07_Base_de_datos.md) | Las 78 tablas con columnas, reglas de la base de datos y diagrama |
| 08 | [Seguridad y permisos](08_Seguridad_y_permisos.md) | Autenticación, cifrado, 12 roles, matriz de 77 permisos |
| 09 | [Instalación y configuración](09_Instalacion_y_configuracion.md) | Instalación en Windows y en servidor Linux, variables de configuración |
| 10 | [Pruebas y validaciones](10_Pruebas_y_validaciones.md) | Estrategia, inventario de pruebas, resultados y criterios de aceptación |
| 11 | [Versiones y cambios (Changelog)](11_Changelog.md) | Historial F0.1 → F5.6 |
| 12 | [Incidencias y soluciones](12_Incidencias_y_soluciones.md) | Problemas encontrados y cómo se resolvieron |
| 13 | [Mantenimiento y operaciones](13_Mantenimiento_y_operaciones.md) | Rutinas diarias, copias, actualizaciones, supervisión, recuperación |
| 14 | [Manual del administrador](14_Manual_administrador.md) | Usuarios, roles, sedes, agentes, copias, auditoría |
| 15 | [Manual del usuario](15_Manual_usuario.md) | Uso por departamento |
| 16 | [Integraciones y APIs](16_Integraciones_y_APIs.md) | Todas las rutas de la API, formatos de intercambio, conectores externos |
| 17 | [Auditoría y trazabilidad](17_Auditoria_y_trazabilidad.md) | Registro inmutable, qué se audita, trazabilidad de los 208 requisitos |
| 18 | [Alineación con el charter de QUBIQ](18_Alineacion_con_el_charter.md) | Diferencias con el *Project Charter*, decisiones pendientes y tomadas (AL-01…AL-13) y criterio para cada necesidad (§2) |
| 19 | [Contabilidad y facturación en Odoo 20](19_Contabilidad_y_facturacion_en_Odoo20.md) | Correspondencia función por función de economía, banco y contabilidad con Odoo 20 Community, OCA y módulos `sp_*` |

Cada documento se entrega en dos formatos: **Word (.docx)**, para leer y compartir, y **Markdown (.md)**, que vive
en el repositorio (`docs/entrega/`) junto al código y se actualiza con él. Se adjunta además `openapi.json` (especificación completa de la API, importable en Postman o Swagger).

## Material de referencia dentro del repositorio
- `referencia/SistemaPropio/`: código de la versión de referencia F5.6c (`apps/api`, `apps/web`,
  `apps/extension-mercurio`) y su documentación interna. Es una copia congelada: no se edita.
- `referencia/SistemaPropio/docs/producto/decisiones.md`: decisiones T-01…T-60 tomadas y abiertas.
- `referencia/SistemaPropio/docs/producto/trazabilidad_codigo.md` y `mapa_cobertura.md`: requisito → código.
- `referencia/SistemaPropio/docs/adr/`: decisiones de arquitectura ADR-0001…0010.
- `referencia/SistemaPropio/docs/pruebas/evidencias_*.md`: evidencias de cada incremento con capturas.
- `referencia/SistemaPropio/docs/fuentes/02_Matriz_Maestra_208_Requisitos.xlsx`: matriz original.

## Datos
Todos los ejemplos, pruebas y capturas usan **datos ficticios**. Ningún documento contiene datos de clientes, del
personal ni claves reales.

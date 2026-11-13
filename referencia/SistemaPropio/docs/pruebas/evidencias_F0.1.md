# Evidencias de pruebas · F0.1

Ejecutadas el 02/11/2026 en el entorno de desarrollo (Linux, Python 3.13, Node 22, PostgreSQL 16.15 local).
Todos los datos son ficticios. Las salidas completas están en `resultado_pytest.txt` y `resultado_vitest.txt`.

## Resumen

| Suite | Resultado | Cómo repetir |
|---|---|---|
| API (pytest, PostgreSQL real) | **49 / 49 superadas** | `cd apps/api && pytest -v` |
| Web (vitest) | **10 / 10 superadas** | `cd apps/web && npm test` |
| Tipos web (tsc) y build de producción (`next build`) | Sin errores | `npm run lint && npm run build` |
| Lint API (ruff) | Sin avisos | `ruff check app tests` |
| Recorrido en navegador (Chrome + web + API + BD) | **11 / 11 pasos** | `npm run e2e` |
| Migración reversible | upgrade → downgrade → upgrade en cada ejecución de tests | `tests/conftest.py` |

## Pruebas de aceptación exigidas

| Prueba | Criterio | Tests automáticos | Captura | Estado |
|---|---|---|---|---|
| **AT-01** Seguridad transversal | Asesor Laboral no lee Extranjería; 403 y se registra | `test_at01_aislamiento_ramas.py` (10 tests: detalle 403 + evento `denied`, listado y filtro sin Extranjería, pestaña de expedientes del contacto, gestor solo asignados, líder solo su rama, Dirección ambas, autorización puntual concede y revoca, solo Dirección concede) | 05, 06 | ✅ Superada |
| **AT-02** Acceso mínimo recepción | Localiza por teléfono con datos minimizados; sin pruebas ni historial | `test_at02_recepcion_minimo.py` (7 tests: respuesta sin teléfono ni documento completos, detalle mínimo, solo metadatos de expedientes, 403 al contenido, 403 al historial, no modifica, no lista sin criterio) | 01, 02, 03 | ✅ Superada |
| **AT-03** Auditoría | Alta, edición y cambio de permisos generan evento irreversible con actor, UTC y recurso | `test_at03_auditoria.py` (5 tests: alta y cambio con antes/después y motivo, offset UTC = 0, lectura sensible, UPDATE/DELETE/TRUNCATE rechazados por BD, cadena de hashes íntegra, solo Dirección consulta) + `grant.create`/`grant.revoke` en AT-01 | 07 | ✅ Superada (descargas: no existen aún, F2.3) |
| **AT-04** Duplicados | Mismo documento → alerta, nunca fusión; teléfono compartido no fusiona | `test_at04_duplicados.py` (4 tests: aviso previo, 409 con candidatos, motivo obligatorio, ambos contactos persisten marcados, cola de revisión; teléfono compartido; validación DNI/NIE/teléfono) | 02, 04 | ✅ Superada |
| **Multiempresa** | Usuario de otra entidad no enumera ni lee | `test_multiempresa_y_ataques.py` (otra entidad: búsqueda solo propia, 404 en detalle/expedientes, no crea en ajena; Soporte Colombia aislado; Dirección multi‑entidad sin Colombia) | — | ✅ Superada |

## Pruebas adversariales adicionales (todas superadas)
IDs aleatorios y malformados · paginación limitada · 6 cargas de inyección SQL y comodines · búsqueda sin tildes ·
sin sesión → 401 · cookie manipulada → 401 · petición sin cabecera CSRF → 403 · cookie `HttpOnly` + `SameSite=Strict` ·
DELETE → 405 y borrado en BD rechazado · expediente con contacto de otra entidad rechazado por trigger ·
control de versión (409) · gestión de documentos solo con permiso · demo prohibido en staging/producción ·
semilla prohibida fuera de desarrollo · OpenAPI bajo `/api/v1` · OIDC responde "No disponible aún" sin simular.

## Recorrido en navegador (capturas en `capturas/`)
1. Recepción entra en modo demo y ve su panel — `01_inicio_recepcion.png`
2. Recepción no puede listar el directorio sin criterio
3. Teléfono compartido: 2 personas distintas, datos enmascarados — `02_busqueda_telefono_compartido_recepcion.png`
4. Ficha mínima y solo metadatos de los dos expedientes de la misma persona — `03_recepcion_ficha_minima_metadatos.png`
5. Alta con NIE válido
6. Letra de control errónea detectada en el formulario
7. Documento repetido: aviso previo y bloqueo hasta confirmar con motivo — `04_aviso_duplicado.png`
8. El listado del asesor laboral no contiene Extranjería — `05_expedientes_asesor_laboral.png`
9. Forzar la URL de un expediente de Extranjería → 403 visible — `06_403_expediente_extranjeria.png`
10. Dirección ve denegaciones y verifica la cadena de auditoría — `07_auditoria_denegaciones_direccion.png`
11. Módulo futuro sin datos simulados — `08_modulo_pendiente_crm.png`

## Lo que NO se ha probado (y por qué)
- **`docker compose up`**: el entorno donde se construyó no tiene servicio Docker. Se verificó por partes (instalación de la API desde `pyproject.toml`, migración y semilla sobre una base vacía, web en modo `standalone` con el recorrido completo de 11 pasos). La construcción de imágenes y `INICIAR.bat` se probarán en el primer Windows con Docker Desktop.
- **CI** (`.github/workflows/ci.yml`): escrito, no ejecutado (no hay repositorio remoto).
- **AT-29** (restauración de copia): fuera de F0.1; planificado en F0.2.
- **Descargas de documentos** en AT-03: no existen documentos hasta F2.3.
- **OIDC/MFA**: no implementado (T-01). Accesibilidad: revisada manualmente (etiquetas, foco, contraste), sin auditoría automática.

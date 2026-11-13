# Evidencias de pruebas · F0.2 (acceso seguro, sesiones, administración y copias)

Ejecutadas el 02/11/2026 en desarrollo (Python 3.13, Node 22, PostgreSQL 16, Chrome). Datos ficticios. Salidas en
`resultado_pytest.txt`, `resultado_vitest.txt` y `resultado_e2e_*.txt`.

## Resumen

| Suite | Resultado |
|---|---|
| API (pytest, PostgreSQL real, migraciones 0001→0003 con bajada y subida) | **106 / 106** (69 anteriores + 37 nuevas) |
| Web (vitest) + tipos (tsc) + build de producción | **13 / 13**, sin errores |
| Recorrido F0.1 en Chrome sobre base vacía | **11 / 11** |
| Recorrido F1.2 + F2 en Chrome sobre base vacía | **11 / 11** |
| Recorrido F0.2 en Chrome (misma base, a continuación) | **13 / 13** |
| Migración 0003 sobre base con datos de F2, bajada y subida | Correcto |
| Copia real (`pg_dump`) + restauración + verificación | Válida: esquema 0003, cadena de auditoría íntegra y coincidente |

## Criterios de aceptación

| Criterio | Evidencia automática | Captura | Estado |
|---|---|---|---|
| Primer acceso obliga a contraseña propia y doble verificación | `test_primer_acceso_obliga_…` | f02_02 | ✅ |
| Cada acceso pide contraseña + código; un código no vale dos veces | `test_acceso_normal_pide_codigo_y_rechaza_reutilizarlo`, `test_totp_tolera_desfase…` | f02_04 | ✅ |
| Mensaje genérico ante usuario o contraseña incorrectos; fallos auditados | `test_contrasena_incorrecta_mensaje_generico…` | — | ✅ |
| Bloqueo tras 5 fallos (contraseña o código), también por IP | `test_bloqueo_*` (3 pruebas) | f02_07 | ✅ |
| Cerrar sesión invalida la cookie al instante | `test_cerrar_sesion_invalida_la_cookie_al_instante` | — | ✅ |
| Revocación desde el perfil o desde Administración, efecto inmediato | `test_cerrar_otra_sesion_propia`, `test_admin_cierra_una_sesion_concreta` | f02_05, f02_06 | ✅ |
| Cierre por inactividad | `test_cierre_por_inactividad` | — | ✅ |
| Cambiar contraseña cierra las demás sesiones | `test_cambio_de_contrasena_cierra_las_demas_sesiones` | f02_03 | ✅ |
| Solo Dirección administra; denegaciones auditadas | `test_solo_direccion_administra_y_se_audita` | recorrido paso 13 | ✅ |
| Alta auditada sin contraseña en la bitácora | `test_alta_de_usuario_auditada_sin_contrasena` | f02_01 | ✅ |
| Cambio de rol con efecto inmediato e historial | `test_cambio_de_rol_tiene_efecto_inmediato` | recorrido paso 10 | ✅ |
| Desactivar cierra sesiones; restablecer exige nuevo primer acceso | `test_desactivar_…`, `test_restablecer_…` | f02_08 | ✅ |
| Nadie se retira a sí mismo; la entidad no queda sin administración | `test_no_puede_quitarse…`, `test_ultima_persona_administradora_protegida` | — | ✅ |
| Sin acción sobre usuarios o sedes de otra entidad | `test_no_se_gestiona…`, `test_sede_o_departamento…`, `test_usuario_compartido…` | — | ✅ |
| OIDC: MFA exigido, firma, estado, sin altas automáticas | `test_f02_oidc.py` (6 pruebas, proveedor simulado) | — | ✅ (falta proveedor real, T-01) |
| **AT-29** copia restaurada y verificada; manipulación detectada | `test_at29_*` (3 pruebas) | f02_09 | ✅ |
| Autorización puntual desde la pantalla | `test_alta_de_autorizacion_desde_formulario` | recorrido paso 11 | ✅ |
| DEMO prohibido fuera de desarrollo; clave de cifrado y MFA obligatorios | `test_configuracion_segura_fuera_de_desarrollo` | — | ✅ |

## Fallos encontrados y corregidos durante esta entrega
- El buscador de autorizaciones fallaba (error 500) para Dirección: el código de expediente es consecutivo **por
  entidad**, y Dirección administra dos entidades con `LAB-2026-0001`. Ahora devuelve todas las coincidencias y la
  pantalla pide elegir la entidad (prueba `test_alta_de_autorizacion_desde_formulario`).
- El bloqueo por intentos se registraba en la auditoría sin vincularlo al usuario: corregido.
- Recorrido F2: un selector ambiguo («Tipo» frente a «Tipo de relación») hacía fallar la prueba en bases con más
  datos; ahora es inequívoco.

## Comprobaciones manuales
- La web reenvía la IP del navegador a la API en `X-Forwarded-For`, pero respeta la que envíe el cliente si ya la
  trae: el límite por IP puede esquivarse falseándola (el límite por usuario no). Documentado como riesgo de
  despliegue: en producción, un proxy inverso debe fijar esa cabecera.
- El script de copia del contenedor (`ops/copia.sh`) se ejecutó con el PostgreSQL 16 local en las mismas condiciones
  (usuario propietario, base `_comprobacion`): copia y restauración correctas.

## No probado (y por qué)
- **Imágenes Docker y `COPIA_SEGURIDAD.bat`**: el entorno de construcción no tiene Docker. Primera ejecución real en
  su Windows.
- **Proveedor OIDC real**: no elegido (T-01). Probado contra un proveedor simulado que firma con RSA.

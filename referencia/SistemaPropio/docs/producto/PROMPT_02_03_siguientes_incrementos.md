# Prompts para los siguientes incrementos

Pegue **uno cada vez**, en este orden, después de revisar la entrega anterior. Ambos se pueden ejecutar ya con datos
ficticios. El PROMPT 02 es requisito antes de cualquier dato real; el PROMPT 03 puede avanzar en paralelo si hay
capacidad, porque no toca la autenticación.

---

## PROMPT 02 — F0.2 Cierre de F0 (seguridad lista para datos reales)

Usa el repositorio SISTEMA PROPIO tal como está (F0.1 en verde) y respeta CLAUDE.md y sus convenciones técnicas. No
rompas ningún test existente; las migraciones deben ser aditivas y reversibles.

Objetivo: cerrar F0 para que el sistema pueda recibir datos reales en un entorno aprobado.

1. **OIDC con MFA** (ADR-0004): implementa `/auth/oidc/login` y `/auth/oidc/callback` (Authorization Code + PKCE, validación de `iss`, `aud`, `nonce`, firma por JWKS). Vincula por `external_subject`; si el `sub` no existe, deniega (alta de usuarios solo por Dirección). Exige el claim de MFA que el proveedor emita (`amr`), configurable. Prueba contra un IdP de pruebas en contenedor (Keycloak de desarrollo) y con tests que simulen tokens firmados con una clave de prueba. Mientras T-01 no esté decidido, el proveedor real queda sin configurar y la pantalla sigue diciendo "No disponible aún".
2. **Sesiones revocables**: tabla `user_session` (jti, usuario, creada, última actividad, revocada); al desactivar un usuario o una pertenencia se revocan todas sus sesiones; test de revocación inmediata.
3. **Administración** (solo Dirección, permiso nuevo `admin.users.manage`): pantallas reales para usuarios, pertenencias (entidad/sede/departamento/rol, con fecha fin) y alta de autorizaciones puntuales (hoy solo por API). Todo cambio de rol o pertenencia se audita con antes/después. Nadie puede concederse permisos a sí mismo (test).
4. **Límite de peticiones** en búsqueda de contactos y en login (por usuario e IP), con respuesta 429 en el formato de error común.
5. **AT-29 Copia y restauración**: script de copia (`pg_dump` cifrado) y restauración en una base de prueba; test automatizado que restaura, verifica recuentos de contactos y expedientes y ejecuta `verify_chain` sobre la auditoría restaurada.
6. **Defensa en profundidad**: rol de BD de la aplicación sin propiedad de las tablas (no puede desactivar triggers); valora Row Level Security para `case_file` como segunda barrera y documenta la decisión en un ADR.
7. Ejecuta CI (`.github/workflows/ci.yml`) y `docker compose up` en una máquina con Docker; documenta el resultado real.

Criterios de aceptación: AT-29 superada; tests de OIDC, revocación, administración, 429 y autoconcesión en verde; los 49 tests de F0.1 siguen en verde; `docs/pruebas/evidencias_F0.2.md` con resultados reales y lo que no se pudo probar.

---

## PROMPT 03 — F1.2 Leads con origen obligatorio (CRM)

Usa el repositorio SISTEMA PROPIO (F0.1, y F0.2 si ya está) y respeta CLAUDE.md. Requisitos: Q-2.1, Q-2.7, Q-2.8,
Q-3.1, I-099, I-102. Pruebas de salida: AT-05 y AT-06 (parcial: hasta "expediente abierto"; el cobro llega en F1.3).

1. **Modelo**: `lead` (organization_id, contact_id → contacto maestro existente o recién creado con aviso de duplicado, origen obligatorio de un catálogo versionable `lead_origin`, campaña, `utm_source/medium/campaign/content/term`, rama de interés, sede, asesor opcional, estado), `lead_event` (transiciones con actor, motivo, fecha UTC). Estados y quién los ejecuta: `docs/producto/estados.md` §1. Sin borrado.
2. **API** `/api/v1/leads`: alta (rechaza sin origen: AT-05), listado con filtros (estado, origen, sede, asesor, rango de fechas) y paginación, detalle, `POST /leads/{id}/transition` con validación de transición y rol. Vincular lead → expediente cuando se abra uno (deja preparado el evento; la apertura completa es F2.1).
3. **Permisos** nuevos en el catálogo: `lead.create`, `lead.read` (entidad y sede), `lead.transition`. Marketing (rol nuevo) ve leads y segmentos pero nunca expedientes ni documentos (test).
4. **Seguimiento TikTok Live / "Teléfono rojo"** (Q-2.8): alertas a 24 h, 72 h y 7 días calculadas desde `lead_event`, mostradas como bandeja "Pendiente de seguimiento"; sin envío automático de mensajes (M12 es F4).
5. **Interfaz**: CRM pasa de "Pendiente" a operativo: bandeja con filtros, ficha del lead enlazada a la ficha del cliente, alta rápida desde la búsqueda de clientes, botones de transición solo si la API los permite.
6. **Embudo** (I-102): endpoint de recuentos por estado/origen/sede/periodo calculado sobre `lead`/`lead_event` (base de AT-27), sin tablas paralelas.
7. Tests: AT-05; trazabilidad lead → contacto → expediente (AT-06 parcial); transición no permitida → 403 auditado; multiempresa; Marketing sin acceso a expedientes; los tests anteriores siguen en verde.

No implementes pagos, envíos de WhatsApp ni correo masivo (Q-2.2 queda para F4 con proveedor y consentimientos aprobados).

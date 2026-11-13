# ADR-0004 · Identidad: OIDC con MFA en producción, modo DEMO solo en desarrollo

- Estado: **Ampliada por ADR-0007** (F0.2: acceso local con MFA, OIDC implementado, sesiones revocables) · Fecha: 02/11/2026

## Decisión
- Producción: proveedor OIDC con MFA obligatorio; el `sub` se guarda en `user_account.external_subject`.
- Desarrollo/tests: `AUTH_MODE=demo` permite elegir usuarios `is_demo`. La configuración **impide arrancar** en `staging` o `production` con modo demo, y exige `COOKIE_SECURE=true` en producción.
- Mientras no exista proveedor, `/auth/oidc/login` responde 501 "No disponible aún"; no se simula ningún acceso.
- Sesión: JWT HS256 firmado con `SESSION_SECRET` (≥32 caracteres, desde entorno o gestor de secretos), 8 h, ligado a `APP_ENV`.

## Pendiente (F0.2)
~~Revocación de sesiones antes de caducar, límite de intentos~~ → resuelto en ADR-0007. Sigue pendiente: rotación
programada de `SESSION_SECRET` (rotarlo hoy cierra todas las sesiones, lo cual es aceptable).

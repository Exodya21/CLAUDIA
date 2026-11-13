# ADR-0007 · Acceso local con doble verificación, OIDC opcional y sesiones revocables

- Estado: **Aceptada como propuesta técnica** (pendiente de validar T-01, T-15, T-16) · Fecha: 02/11/2026

## Contexto
F0.2 debía dejar el sistema apto para datos reales en cuanto a identidad. El proveedor corporativo (T-01) no está
elegido, y esperar bloquearía todo lo demás. El modo DEMO no puede salir de desarrollo.

## Decisión
1. **Métodos combinables** en `AUTH_MODE` (`demo`, `local`, `oidc`). Fuera de desarrollo: `demo` prohibido, `local`
   exige `FIELD_ENCRYPTION_KEY`, `oidc` exige MFA.
2. **Local** = contraseña Argon2id + TOTP (RFC 6238) obligatorio para todos. El alta la hace Dirección con una
   contraseña provisional de un solo uso; el primer acceso obliga a cambiarla y a activar el TOTP con un QR generado
   en el servidor (sin servicios externos). Códigos no reutilizables; tolerancia ±30 s.
3. **OIDC** genérico (código + PKCE S256, `state`, `nonce`, firma por JWKS, emisor y audiencia, MFA en `amr`). No
   crea cuentas: enlaza por correo la primera vez una cuenta dada de alta por Dirección y después por emisor+`sub`.
4. **Sesión = fila en `user_session`** referenciada por el JWT de la cookie. Se comprueba en cada petición:
   revocada, caducada (8 h) o inactiva (60 min) → 401 con motivo. Así la baja de un empleado o la pérdida de un
   dispositivo tiene efecto inmediato.
5. **Límite de intentos** persistido en BD (`auth_attempt`), por usuario (5/15 min) y por IP (30/15 min). Los fallos
   cuentan desde el último acceso completo (con segundo factor).
6. **Administración** de usuarios en el propio sistema (`admin.users.manage`), acotada por entidad, con protección
   del último administrador. Los roles siguen siendo los del catálogo en código (ADR-0003).

## Consecuencias
- Se puede operar con datos reales sin esperar a T-01, siempre que se resuelvan alojamiento y copias (T-02, T-17).
- Cuando se elija proveedor, se añade `oidc` a `AUTH_MODE` y se puede retirar `local` sin migrar datos.
- Recuperación del segundo factor: la hace Dirección (T-15). Sin códigos de recuperación de momento.
- La IP para el límite por IP depende de que un proxy de confianza fije `X-Forwarded-For` (despliegue).

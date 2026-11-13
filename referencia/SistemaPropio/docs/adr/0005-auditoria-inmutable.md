# ADR-0005 · Auditoría inmutable y verificable

- Estado: **Implementado** · Fecha: 02/11/2026 · Requisitos: Q-6.17, I-097, AT-03

## Decisión
- Tabla `audit_event` de solo inserción; triggers rechazan UPDATE, DELETE y TRUNCATE.
- Cada evento guarda el hash del anterior (SHA-256 sobre JSON canónico). `GET /audit-events/verify` recalcula la cadena.
- Escritura serializada con bloqueo consultivo de transacción.
- Cambios auditados en la misma transacción que el cambio (si falla uno, fallan ambos). Denegaciones en transacción propia.
- Se registran: inicios de sesión, búsquedas (criterio y nº de resultados, no el texto buscado), altas, cambios con antes/después y motivo, lecturas de ficha completa y de expediente, denegaciones, autorizaciones.
- Números de documento enmascarados en la bitácora (minimización).

## Límite conocido
Un administrador de base de datos con privilegios de superusuario podría desactivar triggers; la cadena de hashes
permite detectarlo a posteriori. En producción: rol de aplicación sin privilegios de propietario y copia externa
periódica del último hash (F0.2).

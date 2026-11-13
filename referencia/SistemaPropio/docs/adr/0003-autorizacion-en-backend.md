# ADR-0003 · Autorización en backend por entidad, sede, rama, rol y asignación

- Estado: **Implementado como propuesta** · Fecha: 02/11/2026 · Requisitos: Q-1.2, D-13, AT-01, AT-02

## Decisión
- Permisos atómicos agrupados en roles; pertenencias (`membership`) que fijan entidad, sede opcional y departamento.
- Niveles de visibilidad: contacto `full`/`minimal`; expediente `full`/`metadata`.
- La misma regla se expresa como función (`case_level`) y como filtro SQL (`case_visibility_filter`), y los tests comprueban que coinciden en listados y detalle.
- Entidad ajena → 404; misma entidad sin permiso → 403. Ambos auditados como `denied` en transacción propia.
- Autorizaciones puntuales (`access_grant`) con motivo y caducidad ≤30 días, solo a miembros de la entidad.

## Alternativas descartadas
- RLS de PostgreSQL como mecanismo principal: se valorará como capa adicional (defensa en profundidad) en F0.2, pero exige pasar contexto de usuario a cada conexión y complica las pruebas; la regla debe vivir primero en un sitio legible y probado.
- Ocultar en la interfaz: prohibido por el encargo.

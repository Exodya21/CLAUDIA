# Estrategia de pruebas

| Nivel | Herramienta | Qué cubre | Regla |
|---|---|---|---|
| Unidad/servicio | pytest | validaciones, hash de auditoría, configuración | Sin mocks de la BD |
| API + BD | pytest + TestClient + PostgreSQL real | permisos, auditoría, triggers, migraciones | BD `*_test` recreada en cada ejecución (upgrade→downgrade→upgrade) |
| Web unidad | vitest | formato horario Madrid, validación espejo, cliente API, estado de módulos | — |
| Web tipos/build | tsc + next build | contratos de tipos y compilación | Sin errores |
| Extremo a extremo | playwright-core + Chrome (`npm run e2e`) | recorridos por rol con capturas | Contra API y BD reales con datos ficticios |
| Adversariales | pytest | IDOR, SQLi, enumeración, CSRF, borrado, mezcla de entidades | Obligatorios en cada incremento que añada endpoints |

Cada prueba de aceptación AT-xx implementada debe tener al menos un test automático con su ID en el nombre del
fichero o del test, y figurar en `docs/pruebas/evidencias_<incremento>.md` con su resultado REAL (nunca "debería pasar").

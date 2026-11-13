# ADR-0001 · Monolito modular con una sola base de datos

- Estado: **Propuesto** (pendiente de validación de Dirección/TI)
- Fecha: 02/11/2026
- Requisitos: I-120, Q-1.1, Q-1.2, A-12

## Contexto
18 módulos funcionales, ~47 usuarios, un equipo técnico pequeño y una regla de autorización que cruza entidad,
sede, rama, rol y asignación de expediente en casi todas las operaciones.

## Decisión
Una API FastAPI y una base PostgreSQL. Los módulos son paquetes con tablas propias y dependencias explícitas
(ver `docs/producto/arquitectura.md`). La autorización vive en un único motor (`app/security/policy.py`) que todos
los módulos usan. Las integraciones externas se aíslan tras adaptadores y cola (M17).

## Consecuencias
+ Transacciones atómicas entre cambio y auditoría; un único modelo de identidad; despliegue simple.
+ Extraer un módulo más adelante es posible si las fronteras se respetan.
− Exige disciplina en las fronteras (revisión de dependencias en cada incremento).

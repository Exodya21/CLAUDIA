# ADR-0010 — Agentes («motores» de Dirección) dentro del sistema, coordinados por eventos, con bandeja única

- Estado: aceptada (F5.1, 08/11/2026)
- Contexto: Dirección pide «motores» que trabajen solos y se combinen (recepción, contabilidad, RRHH, mensajes) y
  pregunta si hará falta n8n u otra herramienta. Reglas del proyecto: la IA y la automatización proponen; las
  decisiones con efecto jurídico o económico las toma una persona; todo trazable; nada de pantallas que aparenten.

## Decisión
1. Los agentes son **código del propio sistema** (`app/agents/`), no un orquestador externo. Cada agente declara su
   área, los motores de Dirección que cubre (DR-…), los requisitos de la matriz, sus eventos, su calendario y sus
   **límites** (lo que nunca hace), que la pantalla «Agentes» muestra tal cual.
2. **Eventos con patrón outbox**: el cambio que los provoca escribe `agent_event` en la misma transacción
   (`agents.emit`). Se reparten tras la respuesta y cada 5 minutos (`python -m app.ops.agents`). Si un agente falla,
   el cambio original no se pierde, el evento se reintenta (5 veces) y el fallo queda en `agent_run`.
3. **Bandeja única de propuestas** (`agent_proposal`): prioridad, responsable, permiso para decidir y clave de
   deduplicación (la misma propuesta nunca se crea dos veces, tampoco tras rechazarla). Aprobar aplica la propuesta
   con los permisos de la persona; rechazar exige motivo.
4. Modo por agente y entidad: **propone** (por defecto) o **automático**, solo en agentes que lo permiten y solo
   para acciones sin efecto jurídico (T-47). La conciliación bancaria nunca es automática.
5. Reglas deterministas y explicables antes que modelos: cada propuesta lleva su explicación verificable a mano.

## Consecuencias
- Para la empresa entera en un servidor **no hace falta n8n**: basta el contenedor `avisos` (agentes + correo).
  Un orquestador externo solo tendría sentido para integrar terceros sin API propia, y siempre a través de un
  adaptador con cola e idempotencia (regla 11).
- Añadir un agente = una clase en `registry.py`; la bandeja, la auditoría y la pantalla lo recogen solos.
- Próximos: Recepción (cierre diario, DR-REC), RRHH (vencimientos, DR-RH), proveedores y tesorería (DR-CON-4, 7, 8).

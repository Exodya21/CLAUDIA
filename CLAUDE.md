# CLAUDIA · Proyecto del despacho

- **Documentación viva:** `docs/entrega/` (índice en `00_Indice.md`). Consúltala antes de responder sobre el sistema
  y actualízala al terminar cualquier trabajo del proyecto (skill `documentacion-proyecto`): 11 Changelog,
  12 Incidencias, 18 Alineación con el charter y el documento temático. Después regenera los Word con
  `python3 herramientas/docs_a_word.py <prefijos>`.
- **Alcance acordado con QUBIQ (Odoo 20):** skill `sistema-odoo-despacho`.
- **Decisión (13/11/2026): Odoo 20.0 Community para todo el proyecto, sin Enterprise.** Para cada necesidad, en este
  orden: estándar de Odoo 20 Community → módulo de la OCA publicado en 20.0 → desarrollo propio `sp_*` en Odoo 20
  (incluido portar módulos de la OCA 19.0) → externalizar solo si no se puede desarrollar, documentando el motivo
  (ver `docs/entrega/18_…` §2).
- **Super Ficha Laboral:** `LEEME_TRASPASO.md`. Se construye con `python3 herramientas/construir.py`.
- Solo datos ficticios (CLIENTE_01, EXPEDIENTE_01…). Nunca datos personales reales en el repositorio.
- **Agente `documentador`** (`.claude/agents/documentador.md`): registra cada trabajo en la documentación y entrega
  la documentación cuando se pide (`python3 herramientas/paquete_documentacion.py` → `documentacion/entregas/`).
- **Referencia funcional:** `referencia/SistemaPropio/` (Sistema Propio F5.6c, copia congelada; no se edita). Se
  arranca con datos ficticios con `bash herramientas/arrancar_sistema_propio.sh`. Contabilidad y facturación en
  Odoo 20: documento `docs/entrega/19_…`.
